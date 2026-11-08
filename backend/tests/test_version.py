"""The public API reports the source checkout's canonical application version."""

import tomllib

from fastapi.testclient import TestClient

from app.config import BACKEND_ROOT, Settings
from app.main import create_app


def test_openapi_version_matches_project_manifest_outside_backend(tmp_path, monkeypatch):
    with (BACKEND_ROOT / "pyproject.toml").open("rb") as manifest:
        expected = tomllib.load(manifest)["project"]["version"]
    monkeypatch.chdir(tmp_path)
    settings = Settings(data_dir=tmp_path / "state", model_dir=tmp_path / "models")

    with TestClient(create_app(settings)) as client:
        response = client.get("/openapi.json")

    assert response.status_code == 200
    assert response.json()["info"]["version"] == expected
