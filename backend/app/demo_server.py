"""SYNTHETIC API fixture: geometric crops, no real people or recognition claims."""

import argparse
import base64
import io
import json
from typing import Any
from uuid import UUID, uuid4

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from PIL import Image, ImageDraw

LIBRARY_ID = "00000000-0000-4000-8000-000000000001"
GROUP_ID = "00000000-0000-4000-8000-000000000002"
SNAPSHOT_ID = "00000000-0000-4000-8000-000000000003"


def synthetic_jpeg(index: int = 0) -> bytes:
    image = Image.new("RGB", (160, 180), (28, 38 + index % 4 * 12, 43))
    draw = ImageDraw.Draw(image)
    draw.ellipse((45, 25, 115, 115), fill=(140 + index % 3 * 25, 153, 137))
    draw.polygon([(20, 180), (45, 125), (115, 125), (140, 180)], fill=(65, 102, 104))
    draw.text((8, 8), "SYNTHETIC", fill=(235, 240, 225))
    draw.text((8, 157), f"Fixture {index + 1:02d}", fill=(235, 240, 225))
    buffer = io.BytesIO()
    image.save(buffer, "JPEG")
    return buffer.getvalue()


class DemoState:
    def __init__(self, token: str = "synthetic") -> None:
        self.token = token
        self.revision = 7
        self.groups: list[dict[str, Any]] = [
            {
                "id": GROUP_ID,
                "name": "Synthetic existing group",
                "note": "Fixture only",
                "appearance_ids": ["synthetic-01", "outside-current-filter"],
            }
        ]
        self.items: list[dict[str, Any]] = [
            {
                "id": f"synthetic-{index + 1:02d}",
                "clip_id": f"clip-{index // 3 + 1}",
                "source": "Synthetic",
                "camera": "Demo camera",
                "date": "2026-05-25",
                "clock": f"08:57:{index + 40:02d}",
                "seconds": float(index),
                "confidence": 0.95,
                "group_ids": [GROUP_ID] if index == 0 else [],
                "image": {
                    "mime_type": "image/jpeg",
                    "base64": base64.b64encode(synthetic_jpeg(index)).decode(),
                },
            }
            for index in range(12)
        ]
        self.snapshots: dict[str, dict[str, Any]] = {}
        self.imports: dict[str, tuple[bytes, dict[str, Any]]] = {}
        self.requests: list[tuple[str, str, dict[str, str], bytes]] = []
        self.expire_snapshots = False
        self.lose_next_response = False

    def error(self, code: str, message: str, status: int) -> tuple[int, dict[str, Any]]:
        return status, {"code": code, "message": message}

    def handle(
        self,
        method: str,
        path: str,
        params: dict[str, str],
        headers: dict[str, str],
        body: bytes = b"",
    ) -> tuple[int, dict[str, Any]]:
        self.requests.append((method, path, params, body))
        if headers.get("authorization") != f"Bearer {self.token}":
            return self.error("unauthorized", "Use the fixture token.", 401)
        if method == "GET" and path == "/v1/health":
            return 200, {"status": "ok", "library_id": LIBRARY_ID, "revision": self.revision}
        if method == "GET" and path == "/v1/groups":
            return 200, {"library_id": LIBRARY_ID, "revision": self.revision, "items": self.groups}
        if method == "GET" and path == "/v1/appearances":
            if "cursor" in params:
                if len(params) != 1:
                    return self.error(
                        "bad_query", "Later pages must use only cursor in this strict fixture.", 400
                    )
                if self.expire_snapshots or params["cursor"] not in self.snapshots:
                    return self.error("snapshot_gone", "Synthetic snapshot expired.", 410)
                snapshot = self.snapshots[params["cursor"]]
                items, offset = snapshot["items"], snapshot["offset"]
            else:
                if set(params) - {"date", "source", "camera", "limit"}:
                    return self.error("bad_query", "Unknown filter.", 400)
                items = [
                    x
                    for x in self.items
                    if all(x[k] == v for k, v in params.items() if k != "limit")
                ]
                snapshot = {"items": items, "revision": self.revision, "id": str(uuid4())}
                offset = 0
            # Deliberately short pages test correct cursor termination.
            page = items[offset : offset + 3]
            next_offset = offset + len(page)
            cursor = str(uuid4()) if next_offset < len(items) else None
            if cursor:
                self.snapshots[cursor] = {**snapshot, "offset": next_offset}
            return 200, {
                "library_id": LIBRARY_ID,
                "revision": snapshot["revision"],
                "snapshot_id": snapshot["id"],
                "total": len(items),
                "items": page,
                "next_cursor": cursor,
            }
        if method == "POST" and path == "/v1/group-imports":
            if headers.get("content-type") != "application/json":
                return self.error("content_type", "JSON required.", 415)
            if len(body) > 2 * 1024 * 1024:
                return self.error("too_large", "2 MiB maximum.", 413)
            try:
                payload = json.loads(body)
                import_id = str(UUID(payload["import_id"]))
                groups = payload["groups"]
                if not 1 <= len(groups) <= 100:
                    raise ValueError
                for group in groups:
                    UUID(group["id"])
                    if (
                        not 1 <= len(group["name"].strip()) <= 120
                        or len(group.get("note", "")) > 4000
                    ):
                        raise ValueError
                if sum(len(g["appearance_ids"]) for g in groups) > 10000:
                    raise ValueError
            except (ValueError, KeyError, TypeError):
                return self.error("bad_import", "Invalid import.", 400)
            if import_id in self.imports:
                original, result = self.imports[import_id]
                if original != body:
                    return self.error(
                        "import_id_reused", "Use a new ID for changed assignments.", 409
                    )
                return 200, {**result, "current_revision": self.revision, "replayed": True}
            if payload.get("library_id") != LIBRARY_ID:
                return self.error("wrong_library", "Wrong fixture library.", 409)
            if payload.get("base_revision") != self.revision:
                return self.error("revision_conflict", "Fixture groups changed.", 409)
            known = {x["id"] for x in self.items} | {"outside-current-filter"}
            if any(set(g["appearance_ids"]) - known for g in groups):
                return self.error("unknown_appearance", "Unknown fixture appearance.", 422)
            merged = {x["id"]: x for x in self.groups}
            for group in groups:
                merged[group["id"]] = {**group, "note": group.get("note", "")}
            names = [x["name"].strip().casefold() for x in merged.values()]
            if len(names) != len(set(names)):
                return self.error("duplicate_group_name", "Duplicate group name.", 409)
            self.groups = list(merged.values())
            self.revision += 1
            result = {
                "import_id": import_id,
                "revision": self.revision,
                "current_revision": self.revision,
                "group_ids": [g["id"] for g in groups],
                "appearance_count": len({x for g in groups for x in g["appearance_ids"]}),
                "replayed": False,
            }
            self.imports[import_id] = (body, result)
            return 200, result
        return self.error("not_found", "No such fixture endpoint.", 404)


def create_demo_app(token: str = "synthetic") -> FastAPI:
    application = FastAPI(title="SYNTHETIC Footage Review contract fixture")
    state = DemoState(token)
    application.state.demo = state

    @application.api_route("/{path:path}", methods=["GET", "POST"])
    async def route(path: str, request: Request) -> JSONResponse:
        if len(request.query_params.multi_items()) != len(request.query_params):
            return JSONResponse(
                {"code": "bad_query", "message": "Duplicate query key."}, status_code=400
            )
        code, result = state.handle(
            request.method,
            "/" + path,
            dict(request.query_params),
            dict(request.headers),
            await request.body(),
        )
        return JSONResponse(result, status_code=code)

    return application


def main() -> None:
    parser = argparse.ArgumentParser(description="SYNTHETIC Footage Review fixture, no real faces")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument(
        "--token", default="synthetic", help="Fixture credential; never use real tokens"
    )
    args = parser.parse_args()
    print(
        "SYNTHETIC API fixture. Crops are drawings; automatic face extraction should reject them."
    )
    uvicorn.run(create_demo_app(args.token), host="127.0.0.1", port=args.port, access_log=False)


if __name__ == "__main__":
    main()
