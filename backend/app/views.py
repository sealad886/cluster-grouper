import json
from typing import Any
from urllib.parse import quote

from sqlalchemy import func, literal_column, select
from sqlalchemy.orm import Session

from app.database import Appearance, GroupImport, Job, ReviewGroup, Workspace


def job_view(job: Job) -> dict[str, Any]:
    return {
        key: getattr(job, key)
        for key in ("id", "workspace_id", "kind", "status", "phase", "completed", "total", "error")
    }


def group_view(group: ReviewGroup) -> dict[str, Any]:
    return {
        key: getattr(group, key)
        for key in (
            "id",
            "name",
            "note",
            "appearance_ids",
            "origin",
            "reviewed",
            "dirty",
            "similarity",
        )
    }


def import_view(item: GroupImport) -> dict[str, Any]:
    return {
        "id": item.id,
        "status": item.status,
        "payload": json.loads(item.payload_bytes),
        "response": item.response_json,
        "error": item.error,
        "created_at": item.created_at,
    }


def summary_view(session: Session, workspace: Workspace) -> dict[str, Any]:
    count = session.scalar(
        select(func.count()).select_from(Appearance).where(Appearance.workspace_id == workspace.id)
    )
    return {
        "id": workspace.id,
        "name": workspace.name,
        "library_id": workspace.library_id,
        "base_revision": workspace.base_revision,
        "appearance_count": count,
        "created_at": workspace.created_at,
    }


def workspace_view(session: Session, workspace: Workspace) -> dict[str, Any]:
    result = summary_view(session, workspace)
    result["export_complete"] = workspace.export_complete
    result["appearances"] = []
    appearances = session.scalars(
        select(Appearance).where(Appearance.workspace_id == workspace.id).order_by(Appearance.id)
    )
    for appearance in appearances:
        result["appearances"].append(
            {
                **appearance.metadata_json,
                "image_url": (
                    f"/api/workspaces/{workspace.id}/appearances/"
                    f"{quote(appearance.id, safe='')}/image"
                ),
                "embedding_status": appearance.embedding_status,
                "embedding_error": appearance.embedding_error,
            }
        )
    result["groups"] = [
        group_view(group)
        for group in session.scalars(
            select(ReviewGroup)
            .where(ReviewGroup.workspace_id == workspace.id)
            .order_by(ReviewGroup.name)
        )
    ]
    result["jobs"] = [
        job_view(job)
        for job in session.scalars(
            select(Job)
            .where(Job.workspace_id == workspace.id)
            .order_by(literal_column("jobs.rowid"))
        )
    ]
    result["imports"] = [
        import_view(item)
        for item in session.scalars(
            select(GroupImport)
            .where(GroupImport.workspace_id == workspace.id)
            .order_by(GroupImport.created_at.desc())
        )
    ]
    return result
