"""Real owned subprocess tests; all files and data are synthetic and temporary."""

import json
import select
import sqlite3
import subprocess
import sys
from contextlib import closing
from pathlib import Path
from uuid import uuid4

import httpx2
import pytest

from app.config import BACKEND_ROOT
from app.database import Job, Workspace, make_database, uid
from app.managed import MAX_BOOTSTRAP_BYTES


class ManagedChild:
    def __init__(self, data_dir: Path):
        self.secret = "synthetic-bootstrap-" + uuid4().hex
        self.instance_id = str(uuid4()).upper()
        self.process = subprocess.Popen(
            [sys.executable, "-m", "app.managed"],
            cwd=BACKEND_ROOT,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        assert self.process.stdin and self.process.stdout
        self.process.stdin.write(
            (
                json.dumps(
                    {
                        "protocol": 1,
                        "instance_id": self.instance_id,
                        "bootstrap_token": self.secret,
                        "data_dir": str(data_dir),
                    }
                )
                + "\n"
            ).encode()
        )
        self.process.stdin.flush()
        ready, _, _ = select.select([self.process.stdout], [], [], 20)
        if not ready:
            self.close(force=True)
            raise AssertionError("Managed child did not report readiness")
        line = self.process.stdout.readline(4096)
        assert line, "Child exited before readiness"
        response = json.loads(line)
        assert set(response) == {"protocol", "instance_id", "endpoint"}
        assert response["protocol"] == 1 and response["instance_id"] == self.instance_id
        self.endpoint = response["endpoint"]
        assert self.endpoint.startswith("http://127.0.0.1:")
        self.client = httpx2.Client(base_url=self.endpoint, trust_env=False, timeout=5)

    def session(self):
        return self.client.post(
            "/api/session", json={}, headers={"Authorization": "Bearer " + self.secret}
        )

    def close(self, force=False):
        if hasattr(self, "client"):
            self.client.close()
        if self.process.stdin and not self.process.stdin.closed:
            self.process.stdin.close()
        try:
            self.process.wait(timeout=15 if not force else 2)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=3)
            if not force:
                raise AssertionError("Owned child did not exit after parent stdin EOF") from None
        assert self.process.stdout and self.process.stderr
        output, error = self.process.stdout.read(), self.process.stderr.read()
        self.process.stdout.close()
        self.process.stderr.close()
        assert self.secret.encode() not in output + error
        if not force:
            assert self.process.returncode == 0, error
            assert output == b"", "Readiness must be the only stdout line"
            assert error == b""
        return output, error


def test_managed_subprocess_ready_auth_and_parent_eof(tmp_path):
    data_dir = tmp_path / "Clustering"
    child = ManagedChild(data_dir)
    try:
        # The announcement implies both an accepting listener and completed migrations.
        status = child.client.get("/api/status")
        assert status.status_code == 200 and status.json()["session_active"] is False
        with closing(sqlite3.connect(data_dir / "cluster-grouper.sqlite3")) as database:
            assert database.execute("SELECT version_num FROM alembic_version").fetchone()
        assert child.client.post("/api/session", json={}).status_code == 401
        assert (
            child.client.post(
                "/api/session", json={}, headers={"Authorization": "Bearer wrong"}
            ).status_code
            == 401
        )
        assert child.client.get("/api/workspaces").status_code == 401
        connect = {"endpoint": "http://127.0.0.1:8787", "token": "synthetic"}
        assert child.client.post("/api/connect", json=connect).status_code == 401
        assert child.session().json()["session_active"] is True
        assert child.client.get("/api/workspaces").json() == []
        # Bootstrap authentication is limited to session setup, not a second data credential.
        with httpx2.Client(base_url=child.endpoint, trust_env=False) as unprivileged:
            assert (
                unprivileged.get(
                    "/api/workspaces", headers={"Authorization": "Bearer " + child.secret}
                ).status_code
                == 401
            )
    finally:
        endpoint = child.endpoint
        child.close()
    with httpx2.Client(trust_env=False, timeout=1) as client, pytest.raises(httpx2.ConnectError):
        client.get(endpoint + "/api/status")


def test_managed_eof_pauses_durable_active_work_and_restart_retains_it(tmp_path):
    data_dir = tmp_path / "Clustering"
    child = ManagedChild(data_dir)
    assert child.session().status_code == 200
    workspace_id, job_id = uid(), uid()
    try:
        # Synthetic persisted active state models a checkpoint while a unit is in flight.
        # The real canonical lifespan shutdown must mark it paused before process exit.
        from app.config import Settings

        engine, sessions = make_database(Settings(data_dir=data_dir))
        with sessions.begin() as database:
            database.add(
                Workspace(
                    id=workspace_id, name="Synthetic managed run", library_id=uid(), base_revision=7
                )
            )
            database.flush()
            database.add(
                Job(
                    id=job_id,
                    workspace_id=workspace_id,
                    kind="cluster",
                    status="running",
                    completed=3,
                    total=9,
                    checkpoint={},
                )
            )
        engine.dispose()
    finally:
        child.close()
    with closing(sqlite3.connect(data_dir / "cluster-grouper.sqlite3")) as database:
        assert database.execute(
            "SELECT status, completed, total FROM jobs WHERE id=?", (job_id,)
        ).fetchone() == ("paused", 3, 9)
    restarted = ManagedChild(data_dir)
    try:
        assert restarted.client.get("/api/workspaces").status_code == 401
        restarted.session()
        job = restarted.client.get(f"/api/jobs/{job_id}").json()
        assert job["status"] == "paused" and job["completed"] == 3 and job["total"] == 9
        assert restarted.client.get("/api/status").json()["connected"] is False
    finally:
        restarted.close()


@pytest.mark.parametrize("payload", [b"not json\n", b"x" * (MAX_BOOTSTRAP_BYTES + 1)])
def test_managed_invalid_bootstrap_is_bounded_and_never_echoed(payload):
    process = subprocess.run(
        [sys.executable, "-m", "app.managed"],
        cwd=BACKEND_ROOT,
        input=payload,
        capture_output=True,
        timeout=10,
    )
    assert process.returncode == 1
    assert process.stdout == b""
    assert len(process.stderr) < 200 and payload not in process.stderr
