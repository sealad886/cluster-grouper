#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
if [[ ! -x backend/.venv/bin/python ]]; then
  printf '%s\n' 'Project Python is missing. Run make setup first.' >&2
  exit 1
fi
exec backend/.venv/bin/python - <<'PY'
import json
import urllib.error
import urllib.request

all_ready = True
for label, url in (
    ("Browser UI", "http://127.0.0.1:3000"),
    ("Local API", "http://127.0.0.1:8000/api/status"),
):
    try:
        with urllib.request.urlopen(url, timeout=2) as response:
            print(f"{label}: reachable (HTTP {response.status})")
            if label == "Local API":
                status = json.load(response)
                print(f"Models ready: {bool(status.get('models_ready'))}")
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as error:
        print(f"{label}: unavailable ({type(error).__name__})")
        all_ready = False
print("Open http://localhost:3000 to inspect connection and review state.")
raise SystemExit(0 if all_ready else 1)
PY
