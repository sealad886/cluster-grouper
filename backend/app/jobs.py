"""Durable checkpointed worker. One bounded worker thread, one process only."""

import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from fastapi import HTTPException
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session, sessionmaker

from app.clustering import FaceEngine, complete_link_partition, decode_jpeg
from app.config import Settings
from app.database import Appearance, AuditEvent, Job, ReviewGroup, Workspace, uid
from app.errors import IntegrationError
from app.runtime import Runtime

logger = logging.getLogger("cluster.jobs")


class Stopped(Exception):
    pass


class Worker:
    def __init__(self, sessions: sessionmaker, runtime: Runtime, settings: Settings) -> None:  # type: ignore[type-arg]
        self.sessions = sessions
        self.runtime = runtime
        self.settings = settings
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="cluster-worker")
        self.pending: set[str] = set()
        self.pending_lock = threading.Lock()
        self.closed = False

    def recover(self) -> None:
        with self.sessions.begin() as session:
            session.execute(
                update(Job)
                .where(Job.status.in_(["running", "queued"]))
                .values(status="paused", phase="Interrupted by restart — resume when ready")
            )

    def schedule(self, job_id: str) -> None:
        with self.pending_lock:
            if job_id in self.pending:
                return
            self.pending.add(job_id)
        self.executor.submit(self.run, job_id)

    def close(self) -> None:
        self.closed = True
        # Native inference and HTTP requests have bounded units; checkpoint stops next unit.
        with self.sessions.begin() as session:
            session.execute(
                update(Job)
                .where(Job.status.in_(["running", "queued"]))
                .values(status="paused", phase="App closed — resume when ready")
            )
        self.executor.shutdown(wait=True, cancel_futures=True)

    def running(self, session: Session, job_id: str) -> Job:
        job = session.get(Job, job_id, populate_existing=True)
        if self.closed or job is None or job.status not in ("running", "queued"):
            raise Stopped
        return job

    def checkpoint(self, job_id: str, **values: Any) -> None:
        with self.runtime.write_lock, self.sessions.begin() as session:
            job = self.running(session, job_id)
            for name, value in values.items():
                setattr(job, name, value)

    def run(self, job_id: str) -> None:
        try:
            with self.runtime.write_lock, self.sessions.begin() as session:
                job = self.running(session, job_id)
                job.status = "running"
                kind = job.kind
            if kind == "export":
                self.export(job_id)
            else:
                self.cluster(job_id)
        except Stopped:
            pass
        except (IntegrationError, HTTPException) as exc:
            if isinstance(exc, IntegrationError):
                message = f"{exc.code}: {exc.message}"
            else:
                detail = exc.detail
                message = (
                    str(detail.get("message", "Connection required"))
                    if isinstance(detail, dict)
                    else "Connection required"
                )
            self.fail(job_id, message)
        except Exception:
            # Deliberately omit exception/body/traceback: biometric and token data stay out of logs.
            logger.error('{"event":"job_failed","job_id":"%s"}', job_id)
            self.fail(
                job_id,
                "Local processing failed. Check available disk space and restart or export again.",
            )
        finally:
            with self.pending_lock:
                self.pending.discard(job_id)
            # A resume can race with the final checkpoint of the previous invocation.
            with self.sessions() as session:
                job = session.get(Job, job_id)
                restart = job is not None and job.status == "queued" and not self.closed
            if restart:
                self.schedule(job_id)

    def fail(self, job_id: str, message: str) -> None:
        with self.runtime.write_lock, self.sessions.begin() as session:
            job = session.get(Job, job_id)
            if job and job.status in ("running", "queued"):
                job.status, job.phase, job.error = "failed", "Stopped with an error", message
                session.add(AuditEvent(action="job", resource_id=job_id, outcome="failed"))

    def export(self, job_id: str) -> None:
        with self.sessions() as session:
            job = self.running(session, job_id)
            workspace = session.get(Workspace, job.workspace_id)
            assert workspace
            workspace_id, library_id = workspace.id, workspace.library_id
            base_revision = workspace.base_revision
            state = dict(job.checkpoint)
        client = self.runtime.client(library_id)
        if not state.get("groups_saved"):
            groups = client.groups()
            if groups.library_id != library_id or groups.revision != base_revision:
                raise IntegrationError(
                    "revision_changed", "Groups changed before export. Start a fresh export.", 409
                )
            ids = [group.id for group in groups.items]
            names = [group.name.strip().casefold() for group in groups.items]
            if len(set(ids)) != len(ids) or len(set(names)) != len(names):
                raise IntegrationError("invalid_response", "Duplicate groups in API response.")
            with self.runtime.write_lock, self.sessions.begin() as session:
                job = self.running(session, job_id)
                for group in groups.items:
                    session.add(
                        ReviewGroup(
                            workspace_id=workspace_id,
                            id=group.id,
                            name=group.name,
                            note=group.note,
                            appearance_ids=group.appearance_ids,
                            original_appearance_ids=group.appearance_ids,
                            origin="existing",
                            reviewed=True,
                            dirty=False,
                        )
                    )
                state["groups_saved"] = True
                job.checkpoint = state
                job.phase = "Exporting appearance pages"
        while True:
            self.checkpoint(job_id)
            cursor = state.get("cursor")
            params = {"cursor": cursor} if cursor else {**state["filters"], "limit": 20}
            page = client.appearances(params)
            if page.library_id != library_id or page.revision != base_revision:
                raise IntegrationError(
                    "revision_changed",
                    "Library or revision changed during export. Start a fresh export.",
                    409,
                )
            if state.get("snapshot_id") and page.snapshot_id != state["snapshot_id"]:
                raise IntegrationError("snapshot_changed", "API changed the export snapshot.", 409)
            if state.get("total") is not None and page.total != state["total"]:
                raise IntegrationError(
                    "snapshot_changed", "API changed the snapshot appearance count."
                )
            if page.total > 50000:
                raise IntegrationError(
                    "export_too_large",
                    "Use date, source or camera filters for exports above 50,000 appearances.",
                    413,
                )
            seen_cursors = state.get("seen_cursors", [])
            if page.next_cursor is not None and (
                not page.next_cursor
                or page.next_cursor in seen_cursors
                or page.next_cursor == cursor
            ):
                raise IntegrationError("cursor_loop", "API repeated an export cursor.")
            decoded = [(item, decode_jpeg(item.image.base64)) for item in page.items]
            with self.runtime.write_lock, self.sessions.begin() as session:
                job = self.running(session, job_id)
                for item, image in decoded:
                    if session.get(Appearance, (workspace_id, item.id)) is not None:
                        raise IntegrationError(
                            "duplicate_appearance", "API repeated an appearance ID."
                        )
                    metadata = item.model_dump(exclude={"image"})
                    for key in ("source", "camera", "date", "clock"):
                        metadata[key] = metadata[key] or ""
                    session.add(
                        Appearance(
                            workspace_id=workspace_id,
                            id=item.id,
                            metadata_json=metadata,
                            image=image,
                        )
                    )
                job.completed += len(decoded)
                job.total = page.total
                if job.completed > page.total:
                    raise IntegrationError(
                        "invalid_total", "API exported more appearances than the snapshot total."
                    )
                if page.next_cursor is None and job.completed != page.total:
                    raise IntegrationError(
                        "incomplete_export", "API ended before all snapshot appearances arrived."
                    )
                state = {
                    **state,
                    "snapshot_id": page.snapshot_id,
                    "total": page.total,
                    "cursor": page.next_cursor,
                    "seen_cursors": seen_cursors + ([page.next_cursor] if page.next_cursor else []),
                }
                job.checkpoint = state
                if page.next_cursor is None:
                    workspace = session.get(Workspace, workspace_id)
                    assert workspace
                    workspace.export_complete = True
                    job.status, job.phase = "completed", "Export complete"
                    session.add(
                        AuditEvent(action="export", resource_id=workspace_id, outcome="completed")
                    )
                    return

    def cluster(self, job_id: str) -> None:
        engine = FaceEngine(self.settings.model_dir)
        with self.sessions() as session:
            job = self.running(session, job_id)
            workspace_id = job.workspace_id
            parameters = job.checkpoint
            ids = list(
                session.scalars(
                    select(Appearance.id)
                    .where(Appearance.workspace_id == workspace_id)
                    .order_by(Appearance.id)
                )
            )
        for index, appearance_id in enumerate(ids):
            self.checkpoint(
                job_id, phase="Extracting local face features", completed=index, total=len(ids)
            )
            with self.sessions() as session:
                item = session.get(Appearance, (workspace_id, appearance_id))
                assert item
                if item.embedding_status != "pending":
                    continue
                data = item.image
            try:
                vector, error = engine.embed(data), None
            except (ValueError, cv_error()):
                vector, error = (
                    None,
                    "No single usable face with landmarks. Review this crop manually.",
                )
            with self.runtime.write_lock, self.sessions.begin() as session:
                self.running(session, job_id)
                item = session.get(Appearance, (workspace_id, appearance_id))
                assert item
                item.embedding = vector
                item.embedding_status = "ready" if vector else "unusable"
                item.embedding_error = error
        with self.sessions() as session:
            reviewed_members: set[str] = set()
            for group in session.scalars(
                select(ReviewGroup).where(
                    ReviewGroup.workspace_id == workspace_id,
                    (ReviewGroup.reviewed.is_(True)) | (ReviewGroup.origin != "suggested"),
                )
            ):
                reviewed_members.update(group.appearance_ids)
            vectors = {
                item.id: item.embedding
                for item in session.scalars(
                    select(Appearance).where(
                        Appearance.workspace_id == workspace_id,
                        Appearance.embedding_status == "ready",
                    )
                )
                if item.embedding is not None and item.id not in reviewed_members
            }

        def partition_checkpoint(completed: int, total: int) -> None:
            # Check controls between each bounded comparison unit.
            self.checkpoint(
                job_id, phase="Comparing face features", completed=completed, total=total
            )

        suggestions = complete_link_partition(
            vectors, parameters["threshold"], parameters["min_cluster_size"], partition_checkpoint
        )
        with self.runtime.write_lock, self.sessions.begin() as session:
            job = self.running(session, job_id)
            session.execute(
                delete(ReviewGroup).where(
                    ReviewGroup.workspace_id == workspace_id,
                    ReviewGroup.origin == "suggested",
                    ReviewGroup.reviewed.is_(False),
                )
            )
            names = {
                value.strip().casefold()
                for value in session.scalars(
                    select(ReviewGroup.name).where(ReviewGroup.workspace_id == workspace_id)
                )
            }
            for index, suggestion in enumerate(suggestions, 1):
                name = f"Suggested group {index:02d}"
                while name.casefold() in names:
                    name += " new"
                names.add(name.casefold())
                session.add(
                    ReviewGroup(
                        workspace_id=workspace_id,
                        id=uid(),
                        name=name,
                        note="Automatic similarity suggestion. Review every crop before approving.",
                        origin="suggested",
                        reviewed=False,
                        dirty=True,
                        **suggestion,
                    )
                )
            job.status, job.phase = "completed", f"Created {len(suggestions)} groups for review"
            job.completed, job.total = len(ids), len(ids)
            session.add(AuditEvent(action="cluster", resource_id=workspace_id, outcome="completed"))


def cv_error() -> type[Exception]:
    import cv2

    return cv2.error  # type: ignore[no-any-return]
