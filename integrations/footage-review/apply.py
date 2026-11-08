#!/usr/bin/env python3
"""Apply the reviewed native integration to its exact source baseline."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
from datetime import datetime, timezone


def digest(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Footage Review SwiftPM source directory")
    args = parser.parse_args()
    source = args.source.expanduser().resolve(strict=True)
    artifact = Path(__file__).resolve().parent
    changes = json.loads((artifact / "manifest.json").read_text())
    if all(digest(source / name) == item["after"] for name, item in changes.items()):
        print("Native integration already applied.")
        return
    mismatches = [name for name, item in changes.items()
                  if digest(source / name) != item["before"]]
    if mismatches:
        raise SystemExit("Source differs from the reviewed baseline; no files changed:\n"
                         + "\n".join(mismatches))
    command = ["/usr/bin/patch", "--batch", "-E", "-p1", "-i",
               str(artifact / "native-integration.patch")]
    subprocess.run(command + ["--dry-run"], cwd=source, check=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = source / ".integration-backups" / stamp
    backup.mkdir(parents=True, exist_ok=False)
    for name, item in changes.items():
        if item["before"] is not None:
            destination = backup / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source / name, destination)
    (backup / "manifest.json").write_text(json.dumps(changes, indent=2) + "\n")
    subprocess.run(command, cwd=source, check=True)
    failures = [name for name, item in changes.items()
                if digest(source / name) != item["after"]]
    if failures:
        raise SystemExit("Applied source hash mismatch; originals saved in " + str(backup)
                         + ":\n" + "\n".join(failures))
    print(f"Applied {len(changes)} reviewed file changes. Originals: {backup}")


if __name__ == "__main__":
    main()
