"""Durable local review data. Credentials never enter the database."""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    create_engine,
    event,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from app.config import Settings


def uid() -> str:
    return str(uuid4())


def now() -> str:
    return datetime.now(UTC).isoformat()


class Base(DeclarativeBase):
    pass


class Workspace(Base):
    __tablename__ = "workspaces"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(120))
    library_id: Mapped[str] = mapped_column(String)
    base_revision: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[str] = mapped_column(String, default=now)
    export_complete: Mapped[bool] = mapped_column(Boolean, default=False)


class Appearance(Base):
    __tablename__ = "appearances"
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True
    )
    id: Mapped[str] = mapped_column(String, primary_key=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    image: Mapped[bytes] = mapped_column(LargeBinary, deferred=True)
    embedding: Mapped[list[float] | None] = mapped_column(JSON, nullable=True)
    embedding_status: Mapped[str] = mapped_column(String, default="pending")
    embedding_error: Mapped[str | None] = mapped_column(Text, nullable=True)


class ReviewGroup(Base):
    __tablename__ = "review_groups"
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True
    )
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    note: Mapped[str] = mapped_column(Text, default="")
    appearance_ids: Mapped[list[str]] = mapped_column(JSON)
    original_appearance_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    origin: Mapped[str] = mapped_column(String)
    reviewed: Mapped[bool] = mapped_column(Boolean, default=False)
    dirty: Mapped[bool] = mapped_column(Boolean, default=False)
    similarity: Mapped[float | None] = mapped_column(Float, nullable=True)


class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="queued", index=True)
    phase: Mapped[str] = mapped_column(String, default="Waiting")
    completed: Mapped[int] = mapped_column(Integer, default=0)
    total: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    checkpoint: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class GroupImport(Base):
    __tablename__ = "group_imports"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String, default="prepared")
    payload_bytes: Mapped[bytes] = mapped_column(LargeBinary)
    response_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(String, default=now)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[str] = mapped_column(String, default=now)
    action: Mapped[str] = mapped_column(String)
    resource_id: Mapped[str] = mapped_column(String)
    outcome: Mapped[str] = mapped_column(String)


def make_database(settings: Settings) -> tuple[Engine, sessionmaker]:  # type: ignore[type-arg]
    settings.data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    settings.data_dir.chmod(0o700)
    engine = create_engine(
        settings.database_url,
        connect_args={"check_same_thread": False, "timeout": 30},
    )

    @event.listens_for(engine, "connect")
    def configure(connection: Any, _: Any) -> None:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")

    return engine, sessionmaker(engine, expire_on_commit=False)
