import base64
import time
from uuid import uuid4

import httpx2
import pytest
from conftest import export_workspace, wait_job
from fastapi.testclient import TestClient
from sqlalchemy import insert, select

from app.clustering import complete_link_partition, decode_jpeg
from app.database import Appearance, GroupImport, Job, ReviewGroup, Workspace, uid
from app.demo_server import GROUP_ID, LIBRARY_ID, synthetic_jpeg
from app.errors import IntegrationError
from app.footage import FootageClient, validate_endpoint
from app.main import create_app


def test_exports_short_pages_until_null_with_exact_filters_and_bearer(fixture_api):
    client, state, transport, _, _ = fixture_api
    workspace_id = export_workspace(client, camera="Demo camera", date="2026-05-25")
    workspace = client.get(f"/api/workspaces/{workspace_id}").json()
    assert workspace["export_complete"] is True
    assert workspace["appearance_count"] == 12
    assert {item["id"] for item in workspace["appearances"]} == {x["id"] for x in state.items}
    pages = [r for r in state.requests if r[1] == "/v1/appearances"]
    assert len(pages) == 4
    assert pages[0][2] == {"camera": "Demo camera", "date": "2026-05-25", "limit": "20"}
    assert all(set(request[2]) == {"cursor"} for request in pages[1:])
    assert all(headers["authorization"] == "Bearer synthetic" for headers in transport.headers)
    crop = client.get(workspace["appearances"][0]["image_url"])
    assert crop.status_code == 200 and crop.headers["content-type"] == "image/jpeg"
    assert crop.headers["cache-control"] == "no-store"
    assert workspace["groups"][0]["appearance_ids"] == ["synthetic-01", "outside-current-filter"]
    assert not any(r[0] == "POST" for r in state.requests)


def test_empty_export_completes(fixture_api):
    client, *_ = fixture_api
    workspace_id = export_workspace(client, source="No such source")
    result = client.get(f"/api/workspaces/{workspace_id}").json()
    assert result["export_complete"] is True and result["appearance_count"] == 0


def approve_existing(client, workspace_id):
    response = client.patch(
        f"/api/workspaces/{workspace_id}/groups/{GROUP_ID}",
        json={
            "note": "Reviewed locally",
            "reviewed": True,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def prepare(client, workspace_id):
    response = client.post(
        f"/api/workspaces/{workspace_id}/imports", json={"reviewer": "Fixture reviewer"}
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_prepared_import_preserves_full_membership_and_exact_replay(fixture_api):
    client, state, _, app, _ = fixture_api
    workspace_id = export_workspace(client)
    approve_existing(client, workspace_id)
    item = prepare(client, workspace_id)
    assert item["status"] == "prepared"
    assert item["payload"]["base_revision"] == 7
    assert item["payload"]["groups"][0]["appearance_ids"] == [
        "synthetic-01",
        "outside-current-filter",
    ]
    assert state.revision == 7
    url = f"/api/workspaces/{workspace_id}/imports/{item['id']}/submit"
    first = client.post(url, json={}).json()
    assert first["status"] == "submitted" and first["response"]["replayed"] is False
    assert first["response"]["appearance_count"] == 2
    state.revision += 1
    second = client.post(url, json={}).json()
    assert second["response"]["replayed"] is True
    assert second["response"]["revision"] == 8 and second["response"]["current_revision"] == 9
    posts = [r for r in state.requests if r[0] == "POST"]
    assert posts[0][3] == posts[1][3]
    with app.state.sessions() as db:
        saved = db.get(GroupImport, item["id"])
        assert saved.payload_bytes == posts[0][3]
        assert b"synthetic" not in saved.payload_bytes.replace(b"synthetic-01", b"")


def test_lost_import_response_reuses_saved_request_after_restart(fixture_api):
    client, state, transport, app, settings = fixture_api
    workspace_id = export_workspace(client)
    approve_existing(client, workspace_id)
    item = prepare(client, workspace_id)
    state.lose_next_response = True
    url = f"/api/workspaces/{workspace_id}/imports/{item['id']}/submit"
    first = client.post(url, json={}).json()
    assert first["status"] == "uncertain"
    assert state.revision == 8
    # A second app emulates restart: no bearer/session survives, the import bytes do.
    restarted = create_app(settings, transport)
    with TestClient(restarted) as other:
        assert other.get("/api/workspaces").status_code == 401
        other.post("/api/session", json={})
        assert other.get(f"/api/workspaces/{workspace_id}").status_code == 200
        assert other.get("/api/status").json()["connected"] is False
        other.post("/api/connect", json={"endpoint": "http://127.0.0.1:8787", "token": "synthetic"})
        replay = other.post(url, json={}).json()
        assert replay["status"] == "submitted" and replay["response"]["replayed"] is True
    posts = [r for r in state.requests if r[0] == "POST"]
    assert posts[0][3] == posts[1][3]


def test_uppercase_response_uuid_identity_accepts_save_and_exact_replay(fixture_api, monkeypatch):
    client, state, _, app, _ = fixture_api
    workspace_id = export_workspace(client)
    generated_ids = iter(
        [
            "abcdefab-cdef-4abc-8def-abcdefabcdef",
            "fedcba98-7654-4321-8fed-cba987654321",
        ]
    )
    monkeypatch.setattr("app.main.uid", lambda: next(generated_ids))
    group = client.post(
        f"/api/workspaces/{workspace_id}/groups",
        json={
            "name": "UUID case review",
            "note": "Reviewed",
            "appearance_ids": ["synthetic-02"],
            "reviewed": True,
        },
    ).json()
    item = prepare(client, workspace_id)
    original_handle = state.handle

    def uppercase_response(method, path, params, headers, body=b""):
        code, response = original_handle(method, path, params, headers, body)
        if method == "POST" and code == 200:
            response = {
                **response,
                "import_id": response["import_id"].upper(),
                "group_ids": [value.upper() for value in response["group_ids"]],
            }
        return code, response

    monkeypatch.setattr(state, "handle", uppercase_response)
    url = f"/api/workspaces/{workspace_id}/imports/{item['id']}/submit"
    first = client.post(url, json={}).json()
    assert first["status"] == "submitted" and first["response"]["replayed"] is False
    assert first["id"] == item["id"]
    assert first["response"]["import_id"] == item["id"].upper()
    assert first["response"]["group_ids"] == [group["id"].upper()]
    assert first["payload"] == item["payload"]
    second = client.post(url, json={}).json()
    assert second["status"] == "submitted" and second["response"]["replayed"] is True
    posts = [request for request in state.requests if request[0] == "POST"]
    assert posts[0][3] == posts[1][3]
    with app.state.sessions() as database:
        saved = database.get(GroupImport, item["id"])
        assert saved.payload_bytes == posts[0][3]
        local_group = database.get(ReviewGroup, (workspace_id, group["id"]))
        assert local_group.id == group["id"] and local_group.dirty is False
        assert local_group.appearance_ids == ["synthetic-02"]


@pytest.mark.parametrize("field", ["import_id", "group_ids", "malformed_group_ids"])
def test_different_response_uuid_still_leaves_import_uncertain(fixture_api, monkeypatch, field):
    client, state, _, _, _ = fixture_api
    workspace_id = export_workspace(client)
    approve_existing(client, workspace_id)
    item = prepare(client, workspace_id)
    original_handle = state.handle

    def wrong_uuid_response(method, path, params, headers, body=b""):
        code, response = original_handle(method, path, params, headers, body)
        if method == "POST" and code == 200:
            target = "group_ids" if field == "malformed_group_ids" else field
            value = str(uuid4()) if field == "import_id" else [str(uuid4())]
            if field == "malformed_group_ids":
                value = ["invalid-uuid"]
            response = {**response, target: value}
        return code, response

    monkeypatch.setattr(state, "handle", wrong_uuid_response)
    result = client.post(
        f"/api/workspaces/{workspace_id}/imports/{item['id']}/submit", json={}
    ).json()
    assert result["status"] == "uncertain"
    assert "invalid_response" in result["error"]
    assert result["payload"] == item["payload"]
    assert result["payload"]["base_revision"] == 7


def test_conflict_preserves_revision_and_saved_assignments(fixture_api):
    client, state, _, _, _ = fixture_api
    workspace_id = export_workspace(client)
    approve_existing(client, workspace_id)
    item = prepare(client, workspace_id)
    state.revision += 1
    url = f"/api/workspaces/{workspace_id}/imports/{item['id']}/submit"
    result = client.post(url, json={}).json()
    assert result["status"] == "rejected"
    assert result["payload"] == item["payload"]
    assert "revision_conflict" in result["error"]
    assert client.post(url, json={}).status_code == 409
    assert client.post(f"/api/workspaces/{workspace_id}/imports", json={}).status_code == 409


def test_substantive_edit_invalidates_review_and_names_unique(fixture_api):
    client, *_ = fixture_api
    workspace_id = export_workspace(client)
    group = client.patch(
        f"/api/workspaces/{workspace_id}/groups/{GROUP_ID}", json={"note": "Changed note"}
    ).json()
    assert group["reviewed"] is False and group["dirty"] is True
    assert client.post(f"/api/workspaces/{workspace_id}/imports", json={}).status_code == 400
    assert (
        client.post(
            f"/api/workspaces/{workspace_id}/groups",
            json={
                "name": "synthetic EXISTING group",
                "appearance_ids": [],
            },
        ).status_code
        == 409
    )
    assert (
        client.post(
            f"/api/workspaces/{workspace_id}/groups",
            json={
                "name": "Unknown",
                "appearance_ids": ["invented"],
            },
        ).status_code
        == 422
    )
    assert (
        client.request(
            "DELETE", f"/api/workspaces/{workspace_id}/groups/{GROUP_ID}", json={}
        ).status_code
        == 409
    )


def test_new_groups_need_explicit_approval_and_omitted_remote_group_preserved(fixture_api):
    client, state, *_ = fixture_api
    workspace_id = export_workspace(client)
    group = client.post(
        f"/api/workspaces/{workspace_id}/groups",
        json={
            "name": "Human reviewed new group",
            "appearance_ids": ["synthetic-02"],
        },
    ).json()
    assert group["origin"] == "manual" and group["reviewed"] is False
    assert client.post(f"/api/workspaces/{workspace_id}/imports", json={}).status_code == 400
    client.patch(f"/api/workspaces/{workspace_id}/groups/{group['id']}", json={"reviewed": True})
    item = prepare(client, workspace_id)
    assert [g["id"] for g in item["payload"]["groups"]] == [group["id"]]
    result = client.post(
        f"/api/workspaces/{workspace_id}/imports/{item['id']}/submit", json={}
    ).json()
    assert result["status"] == "submitted"
    assert len(state.groups) == 2
    assert next(g for g in state.groups if g["id"] == GROUP_ID)["appearance_ids"] == [
        "synthetic-01",
        "outside-current-filter",
    ]


@pytest.mark.parametrize(
    "fault", ["expired", "revision", "snapshot", "repeated_cursor", "duplicate_id", "short_total"]
)
def test_invalid_pagination_cannot_be_used_for_import(fixture_api, fault):
    client, state, transport, _, _ = fixture_api
    calls = 0

    def corrupt(payload):
        nonlocal calls
        calls += 1
        if calls == 1 and fault == "expired":
            state.expire_snapshots = True
        if calls == 2:
            if fault == "revision":
                payload["revision"] += 1
            elif fault == "snapshot":
                payload["snapshot_id"] = str(uuid4())
            elif fault == "repeated_cursor":
                payload["next_cursor"] = next(iter(state.snapshots))
            elif fault == "duplicate_id":
                payload["items"][0]["id"] = "synthetic-01"
            elif fault == "short_total":
                payload["next_cursor"] = None
        return payload

    transport.page_mutation = corrupt
    created = client.post("/api/exports", json={"name": "Invalid snapshot"}).json()
    job = wait_job(client, created["job_id"])
    assert job["status"] == "failed", job
    workspace = client.get(f"/api/workspaces/{created['workspace_id']}").json()
    assert workspace["export_complete"] is False
    assert workspace["appearance_count"] == 3
    assert (
        client.post(f"/api/workspaces/{created['workspace_id']}/imports", json={}).status_code
        == 409
    )


def test_pause_resume_checkpoint_and_cancel_keep_partial_export_unimportable(fixture_api):
    client, _, transport, _, _ = fixture_api
    transport.block_cursor = True
    created = client.post("/api/exports", json={"name": "Pause test"}).json()
    assert transport.entered.wait(3)
    control_url = f"/api/jobs/{created['job_id']}/control"
    paused = client.post(control_url, json={"action": "pause"}).json()
    assert paused["status"] == "paused" and paused["completed"] == 3
    transport.block_cursor = False
    transport.release.set()
    client.post(control_url, json={"action": "resume"})
    assert wait_job(client, created["job_id"])["status"] == "completed"

    transport.entered.clear()
    transport.release.clear()
    transport.block_cursor = True
    second = client.post("/api/exports", json={"name": "Cancel test"}).json()
    assert transport.entered.wait(3)
    cancelled = client.post(
        f"/api/jobs/{second['job_id']}/control", json={"action": "cancel"}
    ).json()
    assert cancelled["status"] == "cancelled"
    transport.release.set()
    workspace = client.get(f"/api/workspaces/{second['workspace_id']}").json()
    assert workspace["export_complete"] is False and workspace["appearance_count"] == 3


def test_restart_pauses_interrupted_jobs(fixture_api):
    _, _, transport, app, settings = fixture_api
    with app.state.sessions.begin() as db:
        workspace = Workspace(id=uid(), name="Interrupted", library_id=LIBRARY_ID, base_revision=7)
        db.add(workspace)
        db.flush()
        job = Job(
            id=uid(), workspace_id=workspace.id, kind="export", status="running", checkpoint={}
        )
        db.add(job)
        job_id = job.id
    restarted = create_app(settings, transport)
    with TestClient(restarted) as client:
        client.post("/api/session", json={})
        assert client.get(f"/api/jobs/{job_id}").json()["status"] == "paused"


def test_local_auth_origin_boundary_and_token_errors_do_not_echo_input(fixture_api):
    client, _, _, app, _ = fixture_api
    client.cookies.clear()
    assert client.get("/api/workspaces").status_code == 401
    assert (
        client.post("/api/session", json={}, headers={"Origin": "https://evil.example"}).status_code
        == 403
    )
    assert client.get("/api/status", headers={"Host": "evil.example"}).status_code == 400
    secret = "secret-token\ninvalid"
    result = client.post(
        "/api/connect", json={"endpoint": "http://127.0.0.1:8787", "token": secret}
    )
    assert result.status_code == 422 and "secret-token" not in result.text
    result = client.post("/api/session", json={}, headers={"Origin": "http://localhost:3000"})
    assert result.status_code == 200
    assert (
        "HttpOnly" in result.headers["set-cookie"]
        and "SameSite=strict" in result.headers["set-cookie"]
    )
    assert client.get("/api/workspaces").status_code == 200
    client.post("/api/disconnect", json={})
    assert client.get("/api/workspaces").status_code == 200
    assert client.get("/api/status").json()["connected"] is False


@pytest.mark.parametrize(
    "endpoint",
    [
        "https://127.0.0.1:8765",
        "http://localhost:8765",
        "http://192.168.1.2:8765",
        "http://127.0.0.1:8765/a",
        "http://user:secret@127.0.0.1:8765",
        "http://127.0.0.1:8765?x=1",
    ],
)
def test_only_literal_loopback_endpoints_accepted(endpoint):
    with pytest.raises(IntegrationError):
        validate_endpoint(endpoint)


def test_client_will_not_follow_redirects_or_expose_token():
    requests = []

    def handle(request):
        requests.append(request)
        return httpx2.Response(302, headers={"Location": "https://evil.example"})

    client = FootageClient("http://127.0.0.1:8765", "secret", httpx2.MockTransport(handle))
    with pytest.raises(IntegrationError):
        client.health()
    assert len(requests) == 1


def test_similarity_partition_avoids_transitive_chaining():
    vectors = {"a": [1.0, 0.0], "b": [0.8, 0.6], "c": [0.28, 0.96]}
    # a-b and b-c pass .75; a-c fails. No three-member group is valid.
    groups = complete_link_partition(vectors, 0.75, 2)
    assert groups == [{"appearance_ids": ["a", "b"], "similarity": 0.8}]
    assert complete_link_partition(dict(reversed(list(vectors.items()))), 0.75, 2) == groups
    assert complete_link_partition({}, 0.55, 2) == []
    with pytest.raises(ValueError):
        complete_link_partition({"a": [0.0, 0.0]}, 0.55, 2)


@pytest.mark.parametrize("bad_crop", ["not base64", base64.b64encode(b"not jpeg").decode()])
def test_invalid_crop_rejected(bad_crop):
    with pytest.raises(IntegrationError):
        decode_jpeg(bad_crop)
    assert decode_jpeg(base64.b64encode(synthetic_jpeg()).decode()).startswith(b"\xff\xd8")


def test_clustering_creates_unreviewed_suggestions_and_preserves_human_groups(
    fixture_api, monkeypatch
):
    client, _, _, app, _ = fixture_api
    workspace_id = export_workspace(client)
    monkeypatch.setattr("app.main.models_ready", lambda _: (True, "Test vectors"))

    class VectorEngine:
        def __init__(self, _):
            pass

        def embed(self, _):
            return [1.0, 0.0]

    monkeypatch.setattr("app.jobs.FaceEngine", VectorEngine)
    created = client.post(f"/api/workspaces/{workspace_id}/cluster", json={"threshold": 0.9}).json()
    assert wait_job(client, created["job_id"])["status"] == "completed"
    workspace = client.get(f"/api/workspaces/{workspace_id}").json()
    suggested = [g for g in workspace["groups"] if g["origin"] == "suggested"]
    assert len(suggested) == 1 and suggested[0]["reviewed"] is False
    assert "synthetic-01" not in suggested[0]["appearance_ids"]
    assert len(suggested[0]["appearance_ids"]) == 11
    assert client.post(f"/api/workspaces/{workspace_id}/imports", json={}).status_code == 400
    with app.state.sessions() as db:
        assert all(x.embedding_status == "ready" for x in db.scalars(select(Appearance)))


def test_empty_membership_explicitly_clears_existing_group(fixture_api):
    client, state, *_ = fixture_api
    workspace_id = export_workspace(client)
    response = client.patch(
        f"/api/workspaces/{workspace_id}/groups/{GROUP_ID}",
        json={"appearance_ids": [], "reviewed": True},
    )
    assert response.status_code == 200
    item = prepare(client, workspace_id)
    result = client.post(
        f"/api/workspaces/{workspace_id}/imports/{item['id']}/submit", json={}
    ).json()
    assert result["response"]["appearance_count"] == 0
    assert state.groups[0]["appearance_ids"] == []


@pytest.mark.parametrize("case", ["groups", "assignments"])
def test_prepare_enforces_pdf_group_and_total_assignment_bounds(fixture_api, case):
    client, _, _, app, _ = fixture_api
    workspace_id = export_workspace(client)
    with app.state.sessions.begin() as db:
        count = 101 if case == "groups" else 2
        members = [] if case == "groups" else [f"member-{i}" for i in range(5001)]
        for index in range(count):
            db.add(
                ReviewGroup(
                    id=uid(),
                    workspace_id=workspace_id,
                    name=f"Bound fixture {index}",
                    note="",
                    appearance_ids=members,
                    origin="manual",
                    reviewed=True,
                    dirty=True,
                )
            )
    response = client.post(f"/api/workspaces/{workspace_id}/imports", json={})
    assert response.status_code == (400 if case == "groups" else 413)


def test_request_limit_applies_without_content_length(fixture_api):
    client, *_ = fixture_api

    def chunks():
        for _ in range(33):
            yield b"x" * 65536

    response = client.post(
        "/api/session", content=chunks(), headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 413


def test_completed_large_cached_export_can_cluster_more_than_import_assignment_limit(
    fixture_api, monkeypatch
):
    """Local clustering accepts a valid >10k export; upstream import bounds stay separate."""
    client, _, _, app, _ = fixture_api
    workspace_id = uid()
    count = 10001
    crop = synthetic_jpeg()
    ids = [f"large-export-{index:05d}" for index in range(count)]
    with app.state.sessions.begin() as db:
        db.add(
            Workspace(
                id=workspace_id,
                name="Large cached review",
                library_id=LIBRARY_ID,
                base_revision=7,
                export_complete=True,
            )
        )
        db.flush()
        db.execute(
            insert(Appearance),
            [
                {
                    "workspace_id": workspace_id,
                    "id": appearance_id,
                    "metadata_json": {
                        "id": appearance_id,
                        "clip_id": "synthetic-large-clip",
                        "source": "Synthetic",
                        "camera": "Fixture",
                        "date": "2026-05-25",
                        "clock": "08:57:40",
                        "seconds": float(index),
                        "confidence": 0.95,
                        "group_ids": [],
                    },
                    "image": crop,
                    "embedding": [1.0, 0.0],
                    "embedding_status": "ready",
                }
                for index, appearance_id in enumerate(ids)
            ],
        )
    monkeypatch.setattr("app.main.models_ready", lambda _: (True, "Cached synthetic features"))

    class CachedFeaturesOnly:
        def __init__(self, _):
            pass

        def embed(self, _):
            raise AssertionError("Cached crops must not be embedded again")

    def bounded_partition(vectors, threshold, minimum, checkpoint):
        # Algorithm geometry has its own regression. This fixture isolates the
        # public job's capacity contract without a quadratic test workload.
        assert set(vectors) == set(ids)
        checkpoint(count, count)
        return [{"appearance_ids": ids[:2], "similarity": 0.95}]

    monkeypatch.setattr("app.jobs.FaceEngine", CachedFeaturesOnly)
    monkeypatch.setattr("app.jobs.complete_link_partition", bounded_partition)
    response = client.post(f"/api/workspaces/{workspace_id}/cluster", json={"threshold": 0.9})
    assert response.status_code == 200
    job_id = response.json()["job_id"]
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] in ("completed", "failed"):
            break
        time.sleep(0.02)
    assert job["status"] == "completed", job
    assert job["completed"] == count and job["total"] == count
    workspace = client.get(f"/api/workspaces/{workspace_id}").json()
    assert workspace["appearance_count"] == count
    assert len(workspace["groups"]) == 1
    assert workspace["groups"][0]["appearance_ids"] == ids[:2]
    assert workspace["groups"][0]["origin"] == "suggested"
    assert workspace["groups"][0]["reviewed"] is False
