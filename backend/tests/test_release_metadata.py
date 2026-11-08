"""CLI regressions for product version coherence and one scoped version writer."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

CHECKER = Path(__file__).resolve().parents[2] / "scripts/check-release.py"


def write_json(path, value):
    path.write_text(json.dumps(value))


def change_json(path, mutate):
    value = json.loads(path.read_text())
    mutate(value)
    write_json(path, value)


@pytest.fixture
def release_project(tmp_path):
    (tmp_path / "backend").mkdir()
    (tmp_path / "frontend").mkdir()
    (tmp_path / "backend/pyproject.toml").write_text(
        '[project]\nname = "cluster-grouper-backend"\nversion = "0.1.0"\n'
    )
    (tmp_path / "backend/uv.lock").write_text(
        'version = 1\n[[package]]\nname = "another-dependency"\nversion = "8.7.6"\n'
        '[[package]]\nname = "cluster-grouper-backend"\nversion = "0.1.0"\n'
    )
    write_json(
        tmp_path / "frontend/package.json",
        {
            "name": "cluster-grouper-frontend",
            "version": "0.1.0",
            "private": True,
        },
    )
    write_json(
        tmp_path / "frontend/package-lock.json",
        {
            "name": "cluster-grouper-frontend",
            "version": "0.1.0",
            "packages": {
                "": {"name": "cluster-grouper-frontend", "version": "0.1.0"},
                "node_modules/unrelated": {"version": "9.8.7"},
            },
        },
    )
    write_json(
        tmp_path / "release-please-config.json",
        {
            "packages": {
                ".": {
                    "release-type": "python",
                    "component": "cluster-grouper",
                    "package-name": "cluster-grouper",
                    "include-component-in-tag": False,
                    "include-v-in-tag": True,
                    "bump-minor-pre-major": True,
                    "bump-patch-for-minor-pre-major": False,
                    "extra-files": [
                        {
                            "type": "toml",
                            "path": "backend/pyproject.toml",
                            "jsonpath": "$.project.version",
                        },
                        {
                            "type": "toml",
                            "path": "backend/uv.lock",
                            "jsonpath": (
                                "$.package[?(@.name.value == 'cluster-grouper-backend')].version"
                            ),
                        },
                        {"type": "json", "path": "frontend/package.json", "jsonpath": "$.version"},
                        {
                            "type": "json",
                            "path": "frontend/package-lock.json",
                            "jsonpath": "$.version",
                        },
                        {
                            "type": "json",
                            "path": "frontend/package-lock.json",
                            "jsonpath": "$.packages[''].version",
                        },
                    ],
                }
            },
        },
    )
    write_json(tmp_path / ".release-please-manifest.json", {})
    return tmp_path


def run_checker(root, *arguments):
    return subprocess.run(
        [sys.executable, str(CHECKER), "--root", str(root), *arguments],
        cwd=root.parent,
        capture_output=True,
        text=True,
        check=False,
    )


def test_coherent_initial_product_is_reported_unreleased_and_not_mutated(release_project):
    before = {
        path.relative_to(release_project): path.read_bytes()
        for path in release_project.rglob("*")
        if path.is_file()
    }
    result = run_checker(release_project)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["version"] == "0.1.0" and report["release_state"] == "unreleased"
    assert report["tracking_version"] is None and report["publication_verified"] is False
    after = {
        path.relative_to(release_project): path.read_bytes()
        for path in release_project.rglob("*")
        if path.is_file()
    }
    assert after == before


@pytest.mark.parametrize("mirror", ["frontend", "uv", "lock_root", "lock_product"])
def test_inconsistent_product_version_fails_with_affected_path(release_project, mirror):
    if mirror == "uv":
        path = release_project / "backend/uv.lock"
        path.write_text(path.read_text().replace('version = "0.1.0"', 'version = "0.2.0"'))
    else:
        path = release_project / (
            "frontend/package.json" if mirror == "frontend" else "frontend/package-lock.json"
        )

        def change(value):
            target = value["packages"][""] if mirror == "lock_product" else value
            target["version"] = "0.2.0"

        change_json(path, change)
    result = run_checker(release_project)
    assert result.returncode != 0
    assert str(path) in result.stderr


@pytest.mark.parametrize(
    "bad_version", ["01.2.3", "1.02.3", "1.2.03", "1.2", "1.2.3-rc.1", "1.2.3+build"]
)
def test_canonical_version_must_use_enabled_stable_channel(release_project, bad_version):
    path = release_project / "backend/pyproject.toml"
    path.write_text(path.read_text().replace('"0.1.0"', json.dumps(bad_version)))
    result = run_checker(release_project)
    assert result.returncode != 0 and str(path) in result.stderr


def test_dynamic_canonical_version_owner_is_rejected(release_project):
    path = release_project / "backend/pyproject.toml"
    path.write_text(path.read_text() + 'dynamic = ["version"]\n')
    result = run_checker(release_project)
    assert result.returncode != 0 and str(path) in result.stderr


@pytest.mark.parametrize("field", ["name", "private"])
def test_frontend_product_identity_and_nonpublication_policy(release_project, field):
    path = release_project / "frontend/package.json"
    change_json(
        path, lambda value: value.update({field: "another-product" if field == "name" else False})
    )
    result = run_checker(release_project)
    assert result.returncode != 0 and str(path) in result.stderr


@pytest.mark.parametrize(
    "policy",
    [
        "strategy",
        "component",
        "extra_unit",
        "forced_version",
        "prerelease",
        "extra_file",
        "broad_uv_selector",
    ],
)
def test_writer_is_scoped_to_one_product_and_version_fields(release_project, policy):
    path = release_project / "release-please-config.json"

    def change(config):
        unit = config["packages"]["."]
        if policy == "strategy":
            unit["release-type"] = "node"
        elif policy == "component":
            unit["component"] = "another-product"
        elif policy == "extra_unit":
            config["packages"]["frontend"] = {"release-type": "node"}
        elif policy == "forced_version":
            unit["release-as"] = "1.0.0"
        elif policy == "prerelease":
            unit["prerelease"] = True
        elif policy == "extra_file":
            unit["extra-files"].append(
                {"type": "json", "path": "../unrelated/package.json", "jsonpath": "$.version"}
            )
        elif policy == "broad_uv_selector":
            unit["extra-files"][1]["jsonpath"] = "$.package[*].version"

    change_json(path, change)
    result = run_checker(release_project)
    assert result.returncode != 0 and str(path) in result.stderr


def test_explicit_expected_version_must_match_canonical(release_project):
    assert run_checker(release_project, "--expect-version", "0.1.0").returncode == 0
    result = run_checker(release_project, "--expect-version", "0.2.0")
    assert result.returncode != 0 and "backend/pyproject.toml" in result.stderr


def test_future_coherent_tracking_version_is_not_publication_evidence(release_project):
    for relative in (
        "backend/pyproject.toml",
        "backend/uv.lock",
        "frontend/package.json",
        "frontend/package-lock.json",
    ):
        path = release_project / relative
        path.write_text(path.read_text().replace("0.1.0", "0.2.0"))
    write_json(release_project / ".release-please-manifest.json", {".": "0.2.0"})
    result = run_checker(release_project, "--expect-version", "0.2.0")
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["version"] == "0.2.0" and report["tracking_version"] == "0.2.0"
    assert report["publication_verified"] is False


def test_first_python_candidate_must_match_pinned_strategy(release_project):
    for relative in (
        "backend/pyproject.toml",
        "backend/uv.lock",
        "frontend/package.json",
        "frontend/package-lock.json",
    ):
        path = release_project / relative
        path.write_text(path.read_text().replace("0.1.0", "0.2.0"))
    result = run_checker(release_project)
    assert result.returncode != 0 and ".release-please-manifest.json" in result.stderr


@pytest.mark.parametrize(
    "field",
    [
        "include-component-in-tag",
        "include-v-in-tag",
        "bump-minor-pre-major",
        "bump-patch-for-minor-pre-major",
    ],
)
def test_release_tag_and_pre_one_policy_cannot_drift(release_project, field):
    path = release_project / "release-please-config.json"

    def change(config):
        unit = config["packages"]["."]
        unit[field] = not unit[field]

    change_json(path, change)
    result = run_checker(release_project)
    assert result.returncode != 0 and str(path) in result.stderr


@pytest.mark.parametrize("manifest", [{".": "0.2.0"}, {"frontend": "0.1.0"}])
def test_manifest_cannot_disagree_or_add_independent_units(release_project, manifest):
    path = release_project / ".release-please-manifest.json"
    write_json(path, manifest)
    result = run_checker(release_project)
    assert result.returncode != 0 and str(path) in result.stderr


def fixture_git(root, *arguments):
    # Local commits/tags are confined to this disposable fixture; no inherited
    # hooks, signing tools or global Git configuration are allowed to run.
    environment = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
    return subprocess.run(
        [
            "git",
            "--no-pager",
            "-C",
            str(root),
            "-c",
            "user.name=Release Metadata Test",
            "-c",
            "user.email=test@example.invalid",
            "-c",
            f"core.hooksPath={os.devnull}",
            "-c",
            "commit.gpgsign=false",
            "-c",
            "tag.gpgsign=false",
            *arguments,
        ],
        env=environment,
        capture_output=True,
        text=True,
        check=True,
    )


def init_tracked_git_fixture(root):
    write_json(root / ".release-please-manifest.json", {".": "0.1.0"})
    fixture_git(root, "init", "--initial-branch=main")
    fixture_git(root, "add", ".")
    fixture_git(root, "commit", "-m", "test: establish temporary metadata")


def test_first_proposal_requires_no_invented_git_baseline(release_project):
    result = run_checker(release_project, "--require-baseline-tag")
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["release_state"] == "unreleased" and report["git_baseline_tag"] is None
    assert report["publication_verified"] is False


def test_pending_tracking_number_cannot_be_used_for_another_proposal(release_project):
    init_tracked_git_fixture(release_project)
    assert run_checker(release_project).returncode == 0
    result = run_checker(release_project, "--require-baseline-tag")
    assert result.returncode != 0
    assert ".release-please-manifest.json" in result.stderr and "v0.1.0" in result.stderr


def test_reachable_matching_git_tag_allows_proposal_without_publication_claim(release_project):
    init_tracked_git_fixture(release_project)
    fixture_git(release_project, "tag", "v0.1.0")
    (release_project / "notes.txt").write_text("Later local work")
    fixture_git(release_project, "add", "notes.txt")
    fixture_git(release_project, "commit", "-m", "test: advance temporary head")
    result = run_checker(release_project, "--require-baseline-tag")
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["git_baseline_tag"] == "v0.1.0" and report["publication_verified"] is False


def test_tag_outside_head_ancestry_cannot_supply_baseline(release_project):
    init_tracked_git_fixture(release_project)
    fixture_git(release_project, "switch", "--orphan", "unrelated-fixture")
    (release_project / "other.txt").write_text("Unrelated history")
    fixture_git(release_project, "add", "other.txt")
    fixture_git(release_project, "commit", "-m", "test: unrelated temporary history")
    fixture_git(release_project, "tag", "v0.1.0")
    fixture_git(release_project, "switch", "main")
    result = run_checker(release_project, "--require-baseline-tag")
    assert result.returncode != 0
    assert ".release-please-manifest.json" in result.stderr and "v0.1.0" in result.stderr


def test_tagged_canonical_version_must_match_tracking_number(release_project):
    path = release_project / "backend/pyproject.toml"
    original = path.read_text()
    path.write_text(original.replace("0.1.0", "0.0.9"))
    init_tracked_git_fixture(release_project)
    fixture_git(release_project, "tag", "v0.1.0")
    path.write_text(original)
    fixture_git(release_project, "add", "backend/pyproject.toml")
    fixture_git(release_project, "commit", "-m", "test: restore current temporary version")
    result = run_checker(release_project, "--require-baseline-tag")
    assert result.returncode != 0
    assert "backend/pyproject.toml" in result.stderr and "v0.1.0" in result.stderr
