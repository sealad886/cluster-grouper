#!/usr/bin/env bash
# Run the local UI and API; own and stop only the children started here.
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if ! command -v uv >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1; then
  printf '%s\n' 'Install uv and Node.js/npm first, then run make setup.' >&2
  exit 1
fi
if [[ ! -x backend/.venv/bin/python || ! -d frontend/node_modules ]]; then
  printf '%s\n' 'Project dependencies are missing. Run make setup first.' >&2
  exit 1
fi

backend/.venv/bin/python - <<'PY'
import socket
import sys

for port in (8000, 3000):
    with socket.socket() as listener:
        try:
            listener.bind(("127.0.0.1", port))
        except OSError:
            print(f"Port {port} is already in use. No existing process was stopped.", file=sys.stderr)
            sys.exit(1)
PY

printf '%s\n' 'Building the current browser application for local use...'
npm --prefix "$ROOT/frontend" run build
uv run --locked --directory "$ROOT/backend" alembic upgrade head
API_PID=''
UI_PID=''
cleanup() {
  trap - EXIT INT TERM
  for child in "$API_PID" "$UI_PID"; do
    if [[ -n "$child" ]] && kill -0 "$child" 2>/dev/null; then
      kill -TERM "$child" 2>/dev/null || true
    fi
  done
  for child in "$API_PID" "$UI_PID"; do
    if [[ -n "$child" ]]; then
      wait "$child" 2>/dev/null || true
    fi
  done
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

(
  cd backend
  exec .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
) &
API_PID=$!
(
  cd frontend
  exec node node_modules/next/dist/bin/next start --hostname 127.0.0.1 --port 3000
) &
UI_PID=$!

printf 'Cluster Grouper starting. UI: http://localhost:3000\nAPI PID: %s; UI PID: %s\nPress Control-C to stop both services.\n' "$API_PID" "$UI_PID"
while kill -0 "$API_PID" 2>/dev/null && kill -0 "$UI_PID" 2>/dev/null; do
  sleep 1
done
printf '%s\n' 'A local service exited; stopping its sibling.' >&2
exit 1
