"""Single local operator policy and ephemeral upstream credentials."""

import secrets
import threading
from typing import Any

import httpx2
from fastapi import Request

from app.errors import fail
from app.footage import FootageClient

COOKIE_NAME = "cluster_operator"


class Runtime:
    def __init__(self, transport: httpx2.BaseTransport | None = None) -> None:
        self.session_secret = secrets.token_urlsafe(32)
        self.endpoint: str | None = None
        self._token: str | None = None
        self.library_id: str | None = None
        self.revision: int | None = None
        self.transport = transport
        self.write_lock = threading.RLock()
        self.submit_lock = threading.Lock()

    def authorized(self, request: Request) -> bool:
        return secrets.compare_digest(request.cookies.get(COOKIE_NAME, ""), self.session_secret)

    def require_operator(self, request: Request) -> None:
        if not self.authorized(request):
            fail("session_required", "Open the local app to establish an operator session.", 401)

    def connect(self, endpoint: str, token: str) -> None:
        client = FootageClient(endpoint, token, self.transport)
        health = client.health()
        groups = client.groups()
        if groups.library_id != health.library_id or groups.revision != health.revision:
            fail("library_changed", "Library changed during connection. Retry the connection.", 409)
        self.endpoint, self._token = client.endpoint, token
        self.library_id, self.revision = health.library_id, health.revision

    def disconnect(self) -> None:
        self.endpoint, self._token = None, None
        self.library_id, self.revision = None, None

    def client(self, library_id: str | None = None) -> FootageClient:
        if self.endpoint is None or self._token is None:
            fail("connection_required", "Connect to Footage Review with its current token.", 401)
        if library_id is not None and self.library_id != library_id:
            fail("wrong_library", "Connect to the library this workspace was exported from.", 409)
        assert self.endpoint is not None and self._token is not None
        return FootageClient(self.endpoint, self._token, self.transport)


def event(action: str, resource_id: str, outcome: str) -> dict[str, Any]:
    # Contains no names, notes, tokens, crop data or metadata.
    return {"action": action, "resource_id": resource_id, "outcome": outcome}
