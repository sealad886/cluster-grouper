"""FastAPI entry point for the local single-operator application."""

import json
import logging
import secrets
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID

import httpx2
from alembic.config import Config
from fastapi import Depends, FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.middleware.trustedhost import TrustedHostMiddleware

from alembic import command
from app.body_limit import BodyLimitMiddleware
from app.config import BACKEND_ROOT, Settings, application_version
from app.database import (
    Appearance,
    AuditEvent,
    GroupImport,
    Job,
    ReviewGroup,
    Workspace,
    make_database,
    uid,
)
from app.errors import IntegrationError, fail
from app.jobs import Worker
from app.models_setup import models_ready
from app.runtime import COOKIE_NAME, Runtime
from app.schemas import (
    ClusterRequest,
    ConnectRequest,
    ControlRequest,
    ExportCreated,
    ExportRequest,
    GroupFields,
    GroupPatch,
    GroupView,
    ImportView,
    JobCreated,
    JobView,
    OkView,
    PrepareRequest,
    StatusView,
    WorkspaceSummary,
    WorkspaceView,
)
from app.views import group_view, import_view, job_view, summary_view, workspace_view

logger = logging.getLogger("cluster.audit")


def migrate(settings: Settings) -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", settings.database_url)
    command.upgrade(config, "head")
    db = settings.data_dir / "cluster-grouper.sqlite3"
    if db.exists():
        db.chmod(0o600)


def create_app(
    settings: Settings | None = None,
    transport: httpx2.BaseTransport | None = None,
) -> FastAPI:
    settings = settings or Settings()
    runtime = Runtime(transport)
    engine, sessions = make_database(settings)
    worker = Worker(sessions, runtime, settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        migrate(settings)
        worker.recover()
        yield
        worker.close()
        runtime.disconnect()
        engine.dispose()

    application = FastAPI(
        title="Cluster Grouper Local API", version=application_version(), lifespan=lifespan
    )
    application.state.runtime = runtime
    application.state.sessions = sessions
    application.state.worker = worker
    application.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "[::1]", "testserver"]
    )

    @application.middleware("http")
    async def local_boundary(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        origin = request.headers.get("origin")
        if origin and origin not in settings.allowed_origins:
            return JSONResponse(
                {
                    "detail": {
                        "code": "origin_denied",
                        "message": "Use the configured local app origin.",
                    }
                },
                status_code=403,
            )
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            if not origin and request.headers.get("sec-fetch-site") not in (None, "same-origin"):
                return JSONResponse(
                    {
                        "detail": {
                            "code": "origin_denied",
                            "message": "Cross-site local requests are blocked.",
                        }
                    },
                    status_code=403,
                )
            length = request.headers.get("content-length")
            if length and (not length.isdigit() or int(length) > 2 * 1024 * 1024):
                return JSONResponse(
                    {
                        "detail": {
                            "code": "request_too_large",
                            "message": "Request must stay within 2 MiB.",
                        }
                    },
                    status_code=413,
                )
            if request.headers.get("content-type", "").split(";")[0] != "application/json":
                return JSONResponse(
                    {
                        "detail": {
                            "code": "content_type",
                            "message": "Send Content-Type: application/json.",
                        }
                    },
                    status_code=415,
                )
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @application.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        # Never echo input values: connection requests contain bearer credentials.
        fields = ", ".join(".".join(map(str, error["loc"])) for error in exc.errors())
        return JSONResponse(
            {"detail": {"code": "invalid_request", "message": f"Invalid fields: {fields}."}},
            status_code=422,
        )

    @application.exception_handler(IntegrationError)
    async def integration_error(_: Request, exc: IntegrationError) -> JSONResponse:
        return JSONResponse(
            {"detail": {"code": exc.code, "message": exc.message}}, status_code=exc.status
        )

    def session() -> Iterator[Session]:
        with sessions() as value:
            yield value

    def operator(request: Request) -> None:
        runtime.require_operator(request)

    def workspace_or_404(db: Session, workspace_id: str) -> Workspace:
        workspace = db.get(Workspace, workspace_id)
        if not workspace:
            fail("workspace_not_found", "Workspace not found.", 404)
        assert workspace
        return workspace

    def require_complete(workspace: Workspace) -> None:
        if not workspace.export_complete:
            fail(
                "export_incomplete",
                "Complete the export before reviewing groups or clustering.",
                409,
            )

    def audit(db: Session, action: str, resource: str, outcome: str = "ok") -> None:
        db.add(AuditEvent(action=action, resource_id=resource, outcome=outcome))
        logger.info(json.dumps({"action": action, "resource_id": resource, "outcome": outcome}))

    def status(request: Request) -> dict[str, Any]:
        active = runtime.authorized(request)
        ready, message = models_ready(settings.model_dir)
        return {
            "connected": active and runtime.endpoint is not None,
            "session_active": active,
            "library_id": runtime.library_id if active else None,
            "revision": runtime.revision if active else None,
            "models_ready": ready,
            "model_message": message,
        }

    @application.get("/api/status", response_model=StatusView)
    def get_status(request: Request) -> dict[str, Any]:
        return status(request)

    @application.post("/api/session", response_model=StatusView)
    def start_session(request: Request, response: Response) -> dict[str, Any]:
        if settings.managed_bootstrap_token is not None:
            expected = "Bearer " + settings.managed_bootstrap_token
            if not secrets.compare_digest(
                request.headers.get("authorization", "").encode(), expected.encode()
            ):
                fail("bootstrap_required", "Authenticate the native launcher session.", 401)
        response.set_cookie(
            COOKIE_NAME,
            runtime.session_secret,
            httponly=True,
            samesite="strict",
            path="/",
        )
        result = status(request)
        result.update(
            session_active=True,
            connected=runtime.endpoint is not None,
            library_id=runtime.library_id,
            revision=runtime.revision,
        )
        return result

    @application.post("/api/connect", response_model=StatusView)
    def connect(body: ConnectRequest, request: Request, response: Response) -> dict[str, Any]:
        if settings.managed_bootstrap_token is not None:
            runtime.require_operator(request)
        runtime.connect(body.endpoint, body.token)
        response.set_cookie(
            COOKIE_NAME, runtime.session_secret, httponly=True, samesite="strict", path="/"
        )
        result = status(request)
        result.update(
            session_active=True,
            connected=True,
            library_id=runtime.library_id,
            revision=runtime.revision,
        )
        return result

    @application.post("/api/disconnect", dependencies=[Depends(operator)], response_model=OkView)
    def disconnect() -> dict[str, bool]:
        runtime.disconnect()
        return {"ok": True}

    @application.get(
        "/api/workspaces", dependencies=[Depends(operator)], response_model=list[WorkspaceSummary]
    )
    def list_workspaces(db: Session = Depends(session)) -> list[dict[str, Any]]:
        return [
            summary_view(db, item)
            for item in db.scalars(select(Workspace).order_by(Workspace.created_at.desc()))
        ]

    @application.get(
        "/api/workspaces/{workspace_id}",
        dependencies=[Depends(operator)],
        response_model=WorkspaceView,
    )
    def get_workspace(workspace_id: str, db: Session = Depends(session)) -> dict[str, Any]:
        return workspace_view(db, workspace_or_404(db, workspace_id))

    @application.post(
        "/api/exports", dependencies=[Depends(operator)], response_model=ExportCreated
    )
    def export(body: ExportRequest) -> dict[str, str]:
        client = runtime.client()
        groups = client.groups()
        if groups.library_id != runtime.library_id:
            fail("wrong_library", "Connected library changed. Reconnect before export.", 409)
        with runtime.write_lock, sessions.begin() as db:
            workspace = Workspace(
                id=uid(),
                name=body.name,
                library_id=groups.library_id,
                base_revision=groups.revision,
            )
            db.add(workspace)
            db.flush()
            job = Job(
                id=uid(),
                workspace_id=workspace.id,
                kind="export",
                checkpoint={
                    "filters": {
                        k: v
                        for k, v in body.model_dump(exclude={"name"}, exclude_none=True).items()
                        if v
                    },
                },
            )
            db.add(job)
            audit(db, "export_requested", workspace.id)
            result = {"workspace_id": workspace.id, "job_id": job.id}
        runtime.revision = groups.revision
        worker.schedule(job.id)
        return result

    @application.get(
        "/api/workspaces/{workspace_id}/appearances/{appearance_id:path}/image",
        dependencies=[Depends(operator)],
    )
    def image(workspace_id: str, appearance_id: str, db: Session = Depends(session)) -> Response:
        workspace_or_404(db, workspace_id)
        item = db.get(Appearance, (workspace_id, appearance_id))
        if not item:
            fail("appearance_not_found", "Appearance not found.", 404)
        assert item
        return Response(item.image, media_type="image/jpeg", headers={"Cache-Control": "no-store"})

    @application.post(
        "/api/workspaces/{workspace_id}/cluster",
        dependencies=[Depends(operator)],
        response_model=JobCreated,
    )
    def cluster(workspace_id: str, body: ClusterRequest) -> dict[str, str]:
        ready, message = models_ready(settings.model_dir)
        if not ready:
            fail("models_missing", message, 503)
        with runtime.write_lock, sessions.begin() as db:
            workspace = workspace_or_404(db, workspace_id)
            require_complete(workspace)
            active = db.scalar(
                select(Job.id).where(
                    Job.workspace_id == workspace_id,
                    Job.status.in_(["queued", "running", "paused"]),
                )
            )
            if active:
                fail("job_active", "Finish or cancel the existing workspace job first.", 409)
            job = Job(
                id=uid(), workspace_id=workspace_id, kind="cluster", checkpoint=body.model_dump()
            )
            db.add(job)
            audit(db, "cluster_requested", workspace_id)
        worker.schedule(job.id)
        return {"job_id": job.id}

    @application.get("/api/jobs/{job_id}", dependencies=[Depends(operator)], response_model=JobView)
    def get_job(job_id: str, db: Session = Depends(session)) -> dict[str, Any]:
        job = db.get(Job, job_id)
        if not job:
            fail("job_not_found", "Job not found.", 404)
        assert job
        return job_view(job)

    @application.post(
        "/api/jobs/{job_id}/control", dependencies=[Depends(operator)], response_model=JobView
    )
    def control(job_id: str, body: ControlRequest) -> dict[str, Any]:
        with runtime.write_lock, sessions.begin() as db:
            job = db.get(Job, job_id)
            if not job:
                fail("job_not_found", "Job not found.", 404)
            assert job
            if body.action == "resume":
                if job.status != "paused":
                    fail("invalid_job_state", "Only paused jobs can resume.", 409)
                if job.kind == "export":
                    workspace = workspace_or_404(db, job.workspace_id)
                    runtime.client(workspace.library_id)
                job.status, job.error = "queued", None
            elif body.action == "pause":
                if job.status not in ("queued", "running"):
                    fail("invalid_job_state", "Only active jobs can pause.", 409)
                job.status, job.phase = "paused", "Paused at the last durable checkpoint"
            else:
                if job.status not in ("queued", "running", "paused"):
                    fail("invalid_job_state", "This job is already terminal.", 409)
                job.status, job.phase = "cancelled", "Cancelled; completed work retained locally"
            result = job_view(job)
            audit(db, f"job_{body.action}", job_id)
        if body.action == "resume":
            worker.schedule(job_id)
        return result

    def save_group(
        db: Session, workspace_id: str, fields: GroupFields, group: ReviewGroup | None
    ) -> ReviewGroup:
        workspace = workspace_or_404(db, workspace_id)
        require_complete(workspace)
        # Keep edits stable while automatic suggestions are being replaced.
        if (
            db.scalar(
                select(Job.id).where(
                    Job.workspace_id == workspace_id, Job.status.in_(["running", "queued"])
                )
            )
            is not None
        ):
            fail("job_active", "Pause or finish processing before changing groups.", 409)
        groups = list(
            db.scalars(select(ReviewGroup).where(ReviewGroup.workspace_id == workspace_id))
        )
        if any(
            g.id != (group.id if group else None)
            and g.name.strip().casefold() == fields.name.casefold()
            for g in groups
        ):
            fail("duplicate_name", "Choose a unique group name.", 409)
        available = set(
            db.scalars(select(Appearance.id).where(Appearance.workspace_id == workspace_id))
        )
        if group:
            available.update(group.original_appearance_ids)
        if not set(fields.appearance_ids).issubset(available):
            fail(
                "unknown_appearance",
                "Group contains an appearance outside this library export.",
                422,
            )
        if group is None:
            group = ReviewGroup(
                id=uid(), workspace_id=workspace_id, origin="manual", original_appearance_ids=[]
            )
            db.add(group)
        group.name, group.note = fields.name, fields.note
        group.appearance_ids, group.reviewed = fields.appearance_ids, fields.reviewed
        group.dirty = True
        audit(db, "group_edited", group.id)
        db.flush()
        return group

    @application.post(
        "/api/workspaces/{workspace_id}/groups",
        dependencies=[Depends(operator)],
        response_model=GroupView,
    )
    def create_group(workspace_id: str, body: GroupFields) -> dict[str, Any]:
        with runtime.write_lock, sessions.begin() as db:
            return group_view(save_group(db, workspace_id, body, None))

    @application.patch(
        "/api/workspaces/{workspace_id}/groups/{group_id}",
        dependencies=[Depends(operator)],
        response_model=GroupView,
    )
    def patch_group(workspace_id: str, group_id: str, body: GroupPatch) -> dict[str, Any]:
        with runtime.write_lock, sessions.begin() as db:
            group = db.get(ReviewGroup, (workspace_id, group_id))
            if not group:
                fail("group_not_found", "Group not found.", 404)
            assert group
            changes = body.model_dump(exclude_unset=True)
            if any(value is None for value in changes.values()):
                fail("invalid_request", "Group fields cannot be null.", 422)
            current = {k: getattr(group, k) for k in ("name", "note", "appearance_ids", "reviewed")}
            substantive = any(
                key in changes and changes[key] != current[key]
                for key in ("name", "note", "appearance_ids")
            )
            if substantive and "reviewed" not in changes:
                current["reviewed"] = False
            try:
                fields = GroupFields.model_validate({**current, **changes})
            except ValueError:
                fail(
                    "invalid_request",
                    "Check group name, note length and unique membership IDs.",
                    422,
                )
            return group_view(save_group(db, workspace_id, fields, group))

    @application.delete(
        "/api/workspaces/{workspace_id}/groups/{group_id}",
        dependencies=[Depends(operator)],
        response_model=OkView,
    )
    def discard_group(workspace_id: str, group_id: str) -> dict[str, bool]:
        with runtime.write_lock, sessions.begin() as db:
            group = db.get(ReviewGroup, (workspace_id, group_id))
            if not group:
                fail("group_not_found", "Group not found.", 404)
            assert group
            if group.origin == "existing":
                fail(
                    "existing_group",
                    "Existing library groups cannot be discarded here. Edit membership explicitly.",
                    409,
                )
            db.delete(group)
            audit(db, "group_discarded", group_id)
        return {"ok": True}

    @application.post(
        "/api/workspaces/{workspace_id}/imports",
        dependencies=[Depends(operator)],
        response_model=ImportView,
    )
    def prepare_import(workspace_id: str, body: PrepareRequest) -> dict[str, Any]:
        with runtime.write_lock, sessions.begin() as db:
            workspace = workspace_or_404(db, workspace_id)
            require_complete(workspace)
            client = runtime.client(workspace.library_id)
            current = client.groups()
            if (
                current.library_id != workspace.library_id
                or current.revision != workspace.base_revision
            ):
                fail(
                    "revision_conflict",
                    "Groups changed since export. Start a fresh export and reconcile your review.",
                    409,
                )
            groups = list(
                db.scalars(
                    select(ReviewGroup)
                    .where(
                        ReviewGroup.workspace_id == workspace_id,
                        ReviewGroup.reviewed.is_(True),
                        ReviewGroup.dirty.is_(True),
                    )
                    .order_by(ReviewGroup.id)
                )
            )
            if not 1 <= len(groups) <= 100:
                fail(
                    "group_count",
                    "Approve between 1 and 100 changed groups before preparing an import.",
                )
            if sum(len(g.appearance_ids) for g in groups) > 10000:
                fail("assignment_limit", "Import exceeds 10,000 total appearance assignments.", 413)
            import_id = uid()
            payload: dict[str, Any] = {
                "import_id": import_id,
                "library_id": workspace.library_id,
                "base_revision": workspace.base_revision,
                "groups": [
                    {
                        "id": g.id,
                        "name": g.name,
                        "note": g.note,
                        "appearance_ids": g.appearance_ids,
                    }
                    for g in groups
                ],
            }
            if body.reviewer.strip():
                payload["reviewer"] = body.reviewer.strip()
            encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
            if len(encoded) > 2 * 1024 * 1024:
                fail("import_too_large", "Import body exceeds 2 MiB.", 413)
            item = GroupImport(id=import_id, workspace_id=workspace_id, payload_bytes=encoded)
            db.add(item)
            audit(db, "import_prepared", import_id)
            db.flush()
            return import_view(item)

    def get_import(db: Session, workspace_id: str, import_id: str) -> GroupImport:
        item = db.get(GroupImport, import_id)
        if not item or item.workspace_id != workspace_id:
            fail("import_not_found", "Saved import not found.", 404)
        assert item
        return item

    @application.get(
        "/api/workspaces/{workspace_id}/imports/{import_id}",
        dependencies=[Depends(operator)],
        response_model=ImportView,
    )
    def read_import(
        workspace_id: str, import_id: str, db: Session = Depends(session)
    ) -> dict[str, Any]:
        return import_view(get_import(db, workspace_id, import_id))

    @application.post(
        "/api/workspaces/{workspace_id}/imports/{import_id}/submit",
        dependencies=[Depends(operator)],
        response_model=ImportView,
    )
    def submit_import(workspace_id: str, import_id: str) -> dict[str, Any]:
        with runtime.submit_lock:
            with runtime.write_lock, sessions.begin() as db:
                workspace = workspace_or_404(db, workspace_id)
                client = runtime.client(workspace.library_id)
                item = get_import(db, workspace_id, import_id)
                if item.status == "rejected":
                    fail(
                        "import_rejected",
                        "Import rejected. Reconcile in a fresh workspace before preparing again.",
                        409,
                    )
                payload_bytes = item.payload_bytes
                # Durable before network: crash/lost response requires same-body replay.
                item.status, item.error = (
                    "uncertain",
                    "Submission in progress or response uncertain. Retry this saved request.",
                )
                audit(db, "import_submission", import_id, "started")
            try:
                response = client.submit(payload_bytes)
                payload = json.loads(payload_bytes)
                expected_ids = {UUID(g["id"]) for g in payload["groups"]}
                try:
                    identifiers_match = (
                        UUID(response.import_id) == UUID(import_id)
                        and {UUID(group_id) for group_id in response.group_ids} == expected_ids
                    )
                except ValueError:
                    identifiers_match = False
                if not identifiers_match:
                    raise IntegrationError(
                        "invalid_response",
                        "Import response identifiers differ from the saved request.",
                    )
            except IntegrationError as exc:
                with runtime.write_lock, sessions.begin() as db:
                    item = get_import(db, workspace_id, import_id)
                    item.status = (
                        "rejected"
                        if 400 <= exc.status < 500 and exc.status not in (401, 403, 408, 429)
                        else "uncertain"
                    )
                    item.error = f"{exc.code}: {exc.message}"
                    audit(db, "import_submission", import_id, item.status)
                    return import_view(item)
            with runtime.write_lock, sessions.begin() as db:
                item = get_import(db, workspace_id, import_id)
                item.status, item.error, item.response_json = (
                    "submitted",
                    None,
                    response.model_dump(),
                )
                runtime.revision = response.current_revision
                for sent in payload["groups"]:
                    group = db.get(ReviewGroup, (workspace_id, sent["id"]))
                    if group and (group.name, group.note, group.appearance_ids) == (
                        sent["name"],
                        sent["note"],
                        sent["appearance_ids"],
                    ):
                        group.dirty, group.origin = False, "existing"
                        group.original_appearance_ids = group.appearance_ids
                audit(db, "import_submission", import_id, "submitted")
                return import_view(item)

    application.add_middleware(BodyLimitMiddleware)
    return application


# Conventional uvicorn entry point. Only the launcher binds this app, to loopback.
app = create_app()
