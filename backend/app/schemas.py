"""Validated local and Footage Review v1 contracts."""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

Nonnegative = Annotated[int, Field(ge=0, strict=True)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


def valid_uuid(value: str) -> str:
    UUID(value)
    return value


class ConnectRequest(StrictModel):
    endpoint: str = Field(max_length=200)
    token: str = Field(min_length=1, max_length=4096, repr=False)

    @field_validator("token")
    @classmethod
    def token_single_line(cls, value: str) -> str:
        if value != value.strip() or any(ord(c) < 33 or ord(c) > 126 for c in value):
            raise ValueError("Token must contain printable characters without spaces")
        return value


class ExportRequest(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    date: str | None = Field(default=None, max_length=10)
    source: str | None = Field(default=None, max_length=256)
    camera: str | None = Field(default=None, max_length=256)

    @field_validator("name")
    @classmethod
    def trim_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Name cannot be blank")
        return value.strip()

    @field_validator("date")
    @classmethod
    def valid_date(cls, value: str | None) -> str | None:
        if value:
            from datetime import date

            if date.fromisoformat(value).isoformat() != value:
                raise ValueError("Date must use YYYY-MM-DD")
        return value or None


class ClusterRequest(StrictModel):
    threshold: float = Field(default=0.55, ge=0, le=1)
    min_cluster_size: int = Field(default=2, ge=2, le=100)


class ControlRequest(StrictModel):
    action: Literal["pause", "resume", "cancel"]


class GroupFields(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    note: str = Field(default="", max_length=4000)
    appearance_ids: list[str] = Field(default_factory=list, max_length=10000)
    reviewed: bool = False

    @field_validator("name")
    @classmethod
    def trim_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Group name cannot be blank")
        return value.strip()

    @field_validator("appearance_ids")
    @classmethod
    def unique_members(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value) or any(not x or len(x) > 512 for x in value):
            raise ValueError("Membership must contain unique, nonempty appearance IDs")
        return value


class GroupPatch(StrictModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    note: str | None = Field(default=None, max_length=4000)
    appearance_ids: list[str] | None = Field(default=None, max_length=10000)
    reviewed: bool | None = None


class PrepareRequest(StrictModel):
    reviewer: str = Field(default="", max_length=200)


class Health(BaseModel):
    library_id: str
    revision: Nonnegative
    status: str | None = None

    _library_uuid = field_validator("library_id")(valid_uuid)


class RemoteGroup(BaseModel):
    id: str
    name: str = Field(min_length=1, max_length=120)
    note: str = Field(default="", max_length=4000)
    appearance_ids: list[str] = Field(max_length=10000)

    _uuid = field_validator("id")(valid_uuid)


class GroupState(BaseModel):
    library_id: str
    revision: Nonnegative
    items: list[RemoteGroup]

    _library_uuid = field_validator("library_id")(valid_uuid)


class RemoteImage(BaseModel):
    mime_type: Literal["image/jpeg"]
    base64: str = Field(max_length=700000)


class RemoteAppearance(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    id: str = Field(min_length=1, max_length=512)
    clip_id: str = Field(min_length=1, max_length=512)
    source: str | None = None
    camera: str | None = None
    date: str | None = None
    clock: str | None = None
    seconds: float = Field(ge=0)
    confidence: float = Field(ge=0, le=1)
    group_ids: list[str]
    image: RemoteImage


class AppearancePage(BaseModel):
    library_id: str
    revision: Nonnegative
    snapshot_id: str
    total: Nonnegative
    items: list[RemoteAppearance] = Field(max_length=50)
    next_cursor: str | None

    _library_uuid = field_validator("library_id")(valid_uuid)
    _snapshot_uuid = field_validator("snapshot_id")(valid_uuid)


class ImportResponse(BaseModel):
    import_id: str
    revision: Nonnegative
    current_revision: Nonnegative
    group_ids: list[str]
    appearance_count: Nonnegative
    replayed: bool

    _import_uuid = field_validator("import_id")(valid_uuid)


class StatusView(BaseModel):
    connected: bool
    session_active: bool
    library_id: str | None
    revision: int | None
    models_ready: bool
    model_message: str


class WorkspaceSummary(BaseModel):
    id: str
    name: str
    library_id: str
    base_revision: int
    appearance_count: int
    created_at: str


class AppearanceView(BaseModel):
    id: str
    clip_id: str
    source: str
    camera: str
    date: str
    clock: str
    seconds: float
    confidence: float
    group_ids: list[str]
    image_url: str
    embedding_status: Literal["pending", "ready", "unusable"]
    embedding_error: str | None


class GroupView(BaseModel):
    id: str
    name: str
    note: str
    appearance_ids: list[str]
    origin: Literal["existing", "suggested", "manual"]
    reviewed: bool
    dirty: bool
    similarity: float | None


class JobView(BaseModel):
    id: str
    workspace_id: str
    kind: Literal["export", "cluster"]
    status: Literal["queued", "running", "paused", "cancelled", "completed", "failed"]
    phase: str
    completed: int
    total: int
    error: str | None


class ImportView(BaseModel):
    id: str
    status: Literal["prepared", "submitted", "uncertain", "rejected"]
    payload: dict
    response: dict | None
    error: str | None
    created_at: str


class WorkspaceView(WorkspaceSummary):
    export_complete: bool
    appearances: list[AppearanceView]
    groups: list[GroupView]
    jobs: list[JobView]
    imports: list[ImportView]


class ExportCreated(BaseModel):
    workspace_id: str
    job_id: str


class JobCreated(BaseModel):
    job_id: str


class OkView(BaseModel):
    ok: bool = True
