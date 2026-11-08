#!/usr/bin/env python3
"""Check one product's local release metadata; never infer publication or write files.

Requires Python 3.11+. This checker uses only the standard library and no network.
"""

import argparse
import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any

PRODUCT = "cluster-grouper"
BACKEND = "cluster-grouper-backend"
FRONTEND = "cluster-grouper-frontend"
STABLE_VERSION = re.compile(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)")
# These selectors scope the one version writer to product metadata, never dependencies.
EXTRA_FILES = {
    ("toml", "backend/pyproject.toml", "$.project.version"),
    ("toml", "backend/uv.lock", "$.package[?(@.name.value == 'cluster-grouper-backend')].version"),
    ("json", "frontend/package.json", "$.version"),
    ("json", "frontend/package-lock.json", "$.version"),
    ("json", "frontend/package-lock.json", "$.packages[''].version"),
}


class MetadataError(Exception):
    pass


def require(condition: bool, path: Path, message: str) -> None:
    if not condition:
        raise MetadataError(f"{path}: {message}")


def read_object(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
        value = tomllib.loads(text) if path.suffix in (".toml", ".lock") else json.loads(text)
    except (OSError, ValueError) as exc:
        raise MetadataError(f"{path}: cannot read valid metadata ({exc})") from None
    require(isinstance(value, dict), path, "expected a metadata object")
    return value


def stable_version(value: Any, path: Path, field: str) -> str:
    require(
        isinstance(value, str) and STABLE_VERSION.fullmatch(value) is not None,
        path,
        f"{field} must be a stable MAJOR.MINOR.PATCH version without leading zeroes",
    )
    return str(value)


def check_config(root: Path) -> dict[str, Any]:
    path = root / "release-please-config.json"
    config = read_object(path)
    packages = config.get("packages")
    require(
        isinstance(packages, dict) and set(packages) == {"."},
        path,
        "packages must contain exactly the root release unit '.'",
    )
    unit = packages["."]
    require(isinstance(unit, dict), path, "root release unit must be an object")
    require(unit.get("release-type") == "python", path, "root release-type must be python")
    require(unit.get("component") == PRODUCT, path, f"root component must be {PRODUCT}")
    require(unit.get("package-name") == PRODUCT, path, f"root package-name must be {PRODUCT}")
    for field, expected in {
        "include-component-in-tag": False,
        "include-v-in-tag": True,
        "bump-minor-pre-major": True,
        "bump-patch-for-minor-pre-major": False,
    }.items():
        require(unit.get(field) is expected, path, f"root {field} must be {expected}")
    for scope in (config, unit):
        require("release-as" not in scope, path, "release-as overrides are not permitted")
        require(scope.get("prerelease", False) is False, path, "prerelease channel is disabled")
    extras = unit.get("extra-files")
    require(isinstance(extras, list), path, "extra-files must list the product version mirrors")
    actual: list[tuple[str, str, str]] = []
    for entry in extras:
        require(
            isinstance(entry, dict) and set(entry) == {"type", "path", "jsonpath"},
            path,
            "extra-files entries require exactly type, path and jsonpath",
        )
        values = (entry["type"], entry["path"], entry["jsonpath"])
        require(all(isinstance(value, str) for value in values), path, "invalid extra-files entry")
        actual.append(values)
    require(
        len(actual) == len(EXTRA_FILES) and set(actual) == EXTRA_FILES,
        path,
        "extra-files must target only the five product version fields with their typed selectors",
    )
    return config


def check_baseline_tag(root: Path, version: str) -> str:
    """Verify a reachable Git baseline, not publication or provider release state."""
    manifest_path = root / ".release-please-manifest.json"
    tag = f"v{version}"

    def git(*arguments: str) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(
                ["git", "--no-pager", "-C", str(root), *arguments],
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError as exc:
            raise MetadataError(f"{manifest_path}: cannot verify Git baseline ({exc})") from None

    reference = f"refs/tags/{tag}"
    resolved = git("rev-parse", "--verify", reference + "^{commit}")
    require(resolved.returncode == 0, manifest_path, f"required Git baseline tag {tag} is absent")
    ancestry = git("merge-base", "--is-ancestor", resolved.stdout.strip(), "HEAD")
    require(
        ancestry.returncode == 0,
        manifest_path,
        f"Git baseline tag {tag} must be reachable from HEAD",
    )
    tagged = git("show", reference + ":backend/pyproject.toml")
    require(tagged.returncode == 0, manifest_path, f"{tag}:backend/pyproject.toml is unavailable")
    try:
        tagged_version = tomllib.loads(tagged.stdout)["project"]["version"]
    except (ValueError, KeyError, TypeError):
        raise MetadataError(
            f"{manifest_path}: {tag}:backend/pyproject.toml has no static version"
        ) from None
    require(
        tagged_version == version,
        manifest_path,
        f"{tag}:backend/pyproject.toml version must match tracking version {version}",
    )
    return tag


def check(
    root: Path, expect_version: str | None = None, require_baseline_tag: bool = False
) -> dict[str, Any]:
    canonical_path = root / "backend/pyproject.toml"
    canonical = read_object(canonical_path).get("project")
    require(isinstance(canonical, dict), canonical_path, "missing [project] metadata")
    require(canonical.get("name") == BACKEND, canonical_path, f"project.name must be {BACKEND}")
    dynamic = canonical.get("dynamic", [])
    require(isinstance(dynamic, list), canonical_path, "project.dynamic must be a list")
    require("version" not in dynamic, canonical_path, "project.version must have one static owner")
    version = stable_version(canonical.get("version"), canonical_path, "project.version")
    if expect_version is not None:
        stable_version(expect_version, canonical_path, "--expect-version")
        require(version == expect_version, canonical_path, f"version must match {expect_version}")

    uv_path = root / "backend/uv.lock"
    packages = read_object(uv_path).get("package")
    require(isinstance(packages, list), uv_path, "missing package entries")
    own_packages = [
        item for item in packages if isinstance(item, dict) and item.get("name") == BACKEND
    ]
    require(len(own_packages) == 1, uv_path, f"expected exactly one {BACKEND} package")
    require(
        own_packages[0].get("version") == version, uv_path, f"{BACKEND} version must be {version}"
    )

    frontend_path = root / "frontend/package.json"
    frontend = read_object(frontend_path)
    require(frontend.get("name") == FRONTEND, frontend_path, f"name must be {FRONTEND}")
    require(frontend.get("version") == version, frontend_path, f"version must be {version}")
    require(frontend.get("private") is True, frontend_path, "frontend must remain private")

    lock_path = root / "frontend/package-lock.json"
    lock = read_object(lock_path)
    require(lock.get("name") == FRONTEND, lock_path, f"root name must be {FRONTEND}")
    require(lock.get("version") == version, lock_path, f"root version must be {version}")
    lock_packages = lock.get("packages")
    require(isinstance(lock_packages, dict), lock_path, "missing packages object")
    own_lock = lock_packages.get("")
    require(isinstance(own_lock, dict), lock_path, "missing packages[''] product metadata")
    require(own_lock.get("name") == FRONTEND, lock_path, f"packages[''].name must be {FRONTEND}")
    require(
        own_lock.get("version") == version, lock_path, f"packages[''].version must be {version}"
    )

    check_config(root)
    manifest_path = root / ".release-please-manifest.json"
    manifest = read_object(manifest_path)
    require(set(manifest) in (set(), {"."}), manifest_path, "only the root unit may be tracked")
    if manifest:
        tracked = stable_version(manifest["."], manifest_path, "root tracking version")
        require(tracked == version, manifest_path, f"tracking version must match {version}")
    else:
        # The pinned Release Please Python strategy starts a first release at 0.1.0.
        require(
            version == "0.1.0", manifest_path, "empty tracking requires first Python version 0.1.0"
        )
    baseline = (
        check_baseline_tag(root, manifest["."]) if manifest and require_baseline_tag else None
    )
    return {
        "unit": PRODUCT,
        "version": version,
        "release_state": "tracked" if manifest else "unreleased",
        "tracking_version": manifest.get("."),
        "git_baseline_tag": baseline,
        "publication_verified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--expect-version", help="Require an exact stable product version")
    parser.add_argument(
        "--require-baseline-tag",
        action="store_true",
        help="Before proposing another release, require tracked version's tag reachable from HEAD",
    )
    args = parser.parse_args()
    try:
        result = check(args.root.resolve(), args.expect_version, args.require_baseline_tag)
    except MetadataError as exc:
        print(f"Release metadata error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
