import threading
import time

import httpx2
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.demo_server import DemoState
from app.main import create_app


class FixtureTransport(httpx2.BaseTransport):
    def __init__(self, state: DemoState):
        self.state = state
        self.headers = []
        self.block_cursor = False
        self.entered = threading.Event()
        self.release = threading.Event()
        self.page_mutation = None

    def handle_request(self, request):
        self.headers.append(dict(request.headers))
        params = dict(request.url.params)
        if self.block_cursor and "cursor" in params:
            self.entered.set()
            self.release.wait(5)
        status, payload = self.state.handle(
            request.method, request.url.path, params, dict(request.headers), request.content
        )
        if self.page_mutation and request.url.path == "/v1/appearances":
            payload = self.page_mutation(payload)
        if self.state.lose_next_response and request.method == "POST":
            self.state.lose_next_response = False
            raise httpx2.ReadError("Synthetic lost response")
        return httpx2.Response(status, json=payload)


@pytest.fixture
def fixture_api(tmp_path):
    state = DemoState()
    transport = FixtureTransport(state)
    settings = Settings(data_dir=tmp_path / "data", model_dir=tmp_path / "models")
    app = create_app(settings, transport)
    with TestClient(app) as client:
        assert client.post("/api/session", json={}).status_code == 200
        assert (
            client.post(
                "/api/connect", json={"endpoint": "http://127.0.0.1:8787", "token": "synthetic"}
            ).status_code
            == 200
        )
        yield client, state, transport, app, settings
    transport.release.set()


def wait_job(client, job_id, statuses=("completed", "failed", "cancelled")):
    for _ in range(300):
        response = client.get(f"/api/jobs/{job_id}")
        assert response.status_code == 200, response.text
        job = response.json()
        if job["status"] in statuses:
            return job
        time.sleep(0.01)
    raise AssertionError(f"Job did not reach {statuses}: {job}")


def export_workspace(client, **filters):
    response = client.post("/api/exports", json={"name": "Contract review", **filters})
    assert response.status_code == 200, response.text
    created = response.json()
    job = wait_job(client, created["job_id"])
    assert job["status"] == "completed", job
    return created["workspace_id"]
