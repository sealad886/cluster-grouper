"""Owned native child: one stdin bootstrap, one readiness line, graceful EOF cleanup.

This module starts the canonical API. The native coordinator sequences its existing
export, clustering and human-review endpoints; no orchestration is duplicated here.
"""

import asyncio
import json
import logging
import os
import socket
import sys
from pathlib import Path
from typing import Literal
from uuid import UUID

import httpx2
import uvicorn
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.config import BACKEND_ROOT, Settings

MAX_BOOTSTRAP_BYTES = 8192


class Bootstrap(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    protocol: Literal[1]
    instance_id: str = Field(min_length=36, max_length=36)
    bootstrap_token: str = Field(min_length=32, max_length=256, repr=False)
    data_dir: str = Field(min_length=1, max_length=4096)

    @field_validator("instance_id")
    @classmethod
    def instance_uuid(cls, value: str) -> str:
        UUID(value)
        return value  # Echo the exact ID, including the parent's UUID letter casing.

    @field_validator("bootstrap_token")
    @classmethod
    def printable_secret(cls, value: str) -> str:
        if any(ord(c) < 33 or ord(c) > 126 for c in value):
            raise ValueError("Invalid bootstrap credential")
        return value

    @field_validator("data_dir")
    @classmethod
    def absolute_directory(cls, value: str) -> str:
        if not Path(value).is_absolute() or "\x00" in value:
            raise ValueError("Managed data directory must be absolute")
        return value


async def serve(bootstrap: Bootstrap) -> None:
    # Import after a valid bootstrap. No private input is placed in module globals.
    from app.main import create_app

    settings = Settings(
        managed_bootstrap_token=bootstrap.bootstrap_token,
        data_dir=Path(bootstrap.data_dir),
        model_dir=BACKEND_ROOT / ".models",
        allowed_origins=(),
    )
    application = create_app(settings)
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("127.0.0.1", 0))
    listener.listen(128)
    listener.setblocking(False)
    endpoint = f"http://127.0.0.1:{listener.getsockname()[1]}"
    server = uvicorn.Server(
        uvicorn.Config(
            application,
            host="127.0.0.1",
            port=0,
            log_config=None,
            access_log=False,
            proxy_headers=False,
            server_header=False,
            lifespan="on",
            timeout_graceful_shutdown=3,
        )
    )
    loop = asyncio.get_running_loop()
    parent_closed = asyncio.Event()

    def parent_input() -> None:
        try:
            extra = os.read(sys.stdin.fileno(), 1024)
        except OSError:
            extra = b""
        # The protocol permits one bootstrap line only. Extra input also closes the child.
        if extra:
            print("Managed backend protocol input ended unexpectedly.", file=sys.stderr, flush=True)
        parent_closed.set()
        server.should_exit = True
        loop.remove_reader(sys.stdin.fileno())

    loop.add_reader(sys.stdin.fileno(), parent_input)
    task = asyncio.create_task(server.serve(sockets=[listener]))
    try:
        while not server.started and not task.done() and not parent_closed.is_set():
            await asyncio.sleep(0.01)
        if task.done():
            await task
            raise RuntimeError("Listener did not become ready")
        if not parent_closed.is_set():
            # Confirm a real request completes after migration/lifespan and listener startup.
            async with httpx2.AsyncClient(
                trust_env=False, follow_redirects=False, timeout=3
            ) as client:
                response = await client.get(endpoint + "/api/status")
                response.raise_for_status()
            if not parent_closed.is_set():
                print(
                    json.dumps(
                        {
                            "protocol": 1,
                            "instance_id": bootstrap.instance_id,
                            "endpoint": endpoint,
                        },
                        separators=(",", ":"),
                    ),
                    flush=True,
                )
        await task
    finally:
        loop.remove_reader(sys.stdin.fileno())
        server.should_exit = True
        if not task.done():
            await task
        listener.close()


def main() -> int:
    # Third-party exception logging can include database values. Managed stderr is
    # deliberately limited to fixed, redacted operational errors emitted below.
    logging.disable(logging.CRITICAL)
    try:
        line = sys.stdin.buffer.readline(MAX_BOOTSTRAP_BYTES + 1)
        if not line:
            return 0
        if len(line) > MAX_BOOTSTRAP_BYTES or not line.endswith(b"\n"):
            raise ValueError("Invalid bootstrap line")
        bootstrap = Bootstrap.model_validate_json(line)
        asyncio.run(serve(bootstrap))
        return 0
    except KeyboardInterrupt:
        return 0
    except (Exception, SystemExit):
        print(
            "Managed backend could not start or stopped unexpectedly.", file=sys.stderr, flush=True
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
