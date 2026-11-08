"""Bounded, authenticated client for the supplied Footage Review API reference."""

import ipaddress
import json
from typing import Any, TypeVar
from urllib.parse import urlsplit

import httpx2
from pydantic import BaseModel, ValidationError

from app.errors import IntegrationError
from app.schemas import AppearancePage, GroupState, Health, ImportResponse

Model = TypeVar("Model", bound=BaseModel)


def validate_endpoint(endpoint: str) -> str:
    try:
        parsed = urlsplit(endpoint)
        address = ipaddress.ip_address(parsed.hostname or "")
        if (
            parsed.scheme != "http"
            or not address.is_loopback
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in ("", "/")
            or parsed.query
            or parsed.fragment
            or parsed.port is None
            or not 1 <= parsed.port <= 65535
        ):
            raise ValueError
    except ValueError as exc:
        raise IntegrationError(
            "invalid_endpoint", "Use an HTTP loopback IP endpoint with an explicit port.", 400
        ) from exc
    return endpoint.rstrip("/")


class FootageClient:
    def __init__(
        self, endpoint: str, token: str, transport: httpx2.BaseTransport | None = None
    ) -> None:
        self.endpoint = validate_endpoint(endpoint)
        self._token = token
        self._transport = transport

    def request(
        self,
        method: str,
        path: str,
        model: type[Model],
        *,
        params: dict[str, str | int] | None = None,
        body: bytes | None = None,
    ) -> Model:
        headers = {"Authorization": f"Bearer {self._token}", "Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        try:
            with httpx2.Client(
                timeout=httpx2.Timeout(12, connect=3),
                follow_redirects=False,
                trust_env=False,
                transport=self._transport,
            ) as client:
                with client.stream(
                    method, self.endpoint + path, headers=headers, params=params, content=body
                ) as response:
                    chunks = bytearray()
                    for chunk in response.iter_bytes():
                        chunks.extend(chunk)
                        if len(chunks) > 8 * 1024 * 1024:
                            raise IntegrationError(
                                "response_too_large",
                                "API response exceeds the documented 8 MiB limit.",
                            )
                    if response.status_code != 200:
                        try:
                            error = json.loads(chunks)
                        except (ValueError, UnicodeDecodeError):
                            error = {}
                        if not isinstance(error, dict):
                            error = {}
                        code = str(error.get("code", f"upstream_{response.status_code}"))[:120]
                        message = str(error.get("message", "Footage Review rejected the request."))
                        message = message.replace(self._token, "[redacted]")[:500]
                        code = code.replace(self._token, "[redacted]")
                        if response.status_code == 410:
                            message += (
                                " Start a fresh export; existing review decisions are preserved."
                            )
                        if response.status_code == 409:
                            message += (
                                " Reconcile with a fresh export; do not change the saved revision."
                            )
                        raise IntegrationError(code, message, response.status_code)
                    if "application/json" not in response.headers.get("content-type", ""):
                        raise IntegrationError("invalid_response", "API did not return JSON.")
                    try:
                        return model.model_validate_json(chunks)
                    except ValidationError as exc:
                        raise IntegrationError(
                            "invalid_response",
                            "API response does not match the documented v1 contract.",
                        ) from exc
        except httpx2.HTTPError as exc:
            raise IntegrationError(
                "connection_failed",
                "Cannot reach Footage Review. Check its API, endpoint and token.",
                503,
            ) from exc

    def health(self) -> Health:
        return self.request("GET", "/v1/health", Health)

    def groups(self) -> GroupState:
        return self.request("GET", "/v1/groups", GroupState)

    def appearances(self, params: dict[str, Any]) -> AppearancePage:
        return self.request("GET", "/v1/appearances", AppearancePage, params=params)

    def submit(self, payload: bytes) -> ImportResponse:
        return self.request("POST", "/v1/group-imports", ImportResponse, body=payload)
