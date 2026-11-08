# Local operations runbook

## Environment

Run on the same Mac as Footage Review. Native 1.3.0 (build 4) starts its own managed Python child; it needs no Node.js or browser server. The optional browser launch starts one standalone backend and frontend. All listeners bind to loopback. Use one backend process per state directory.

## Native setup and operation

Prepare the Python environment and verified models once from this repository:

```bash
uv sync --directory backend --python 3.13 --locked --extra dev
make models
```

Open Footage Review 1.3.0. In **Settings → Clustering**, select this repository and inspect setup/model status. Choose exact date, source and camera scope, or **All** for each. Set similarity and minimum group size, then click **Cluster Faces**. The app starts/reuses its integration API, launches its own backend, connects without token copying, exports detections and clusters locally. The main window's filters and selection do not define this scope.

Use native **Pause**, **Resume**, **Cancel** and **Review Suggestions** controls. Save reviewed groups, choose **Prepare Import**, inspect the immutable preview and explicitly submit. Each export supports up to 50,000 appearances; each import separately permits up to 100 groups, 10,000 assignments and 2 MiB. No scan or import occurs merely because clustering starts.

The native database and `NativeRun.json` receipt live in `<library>/Clustering`. Saved runs keep their original scope and parameters. Use **Start New Clustering Run** to apply changed settings after the current run is completed or cancelled. Quit defers termination for owned-child cleanup; parent stdin EOF asks the backend to pause unfinished jobs and shut down. **Settings → Clustering → Stop Clustering Service** stops the owned child when idle. A manually started Footage Review API is not stopped when a clustering run ends.

**Settings → General** reveals the library location. **Settings → Integrations** retains manual API controls; the native Python client needs no browser-origin value. The [native contract](native-integration-contract.md) specifies the process/authentication protocol and [native delivery guide](../integrations/footage-review/README.md) covers integration artifacts.

If the integration API reports a port conflict, choose an unused port in Settings → Integrations; do not stop an unrelated service. On this Mac, SpeechForge already uses 8765, so Footage Review is configured for 18765. A backend startup timeout leaves saved work intact: retry Cluster Faces, and check the selected tool folder/environment if the timeout repeats. One first-start timeout was observed during GUI validation; later startup and service restart passed.

## Optional browser setup and start

From the repository root:

```bash
make setup
make models
make run
```

Open `http://localhost:3000` after startup finishes. The launcher checks its ports, builds the current frontend, runs the database migration, and starts the backend plus the frontend's production server. It rebuilds on each launch so normal use reflects the current source. Press Control-C to stop both owned child processes. It does not stop unrelated listeners. If a service exits unexpectedly, the launcher stops its sibling and returns failure.

Run `make status` from another terminal to inspect local availability. If a port is occupied, stop the application that owns it or use that app's existing instance; the launcher never kills a listener it did not start.

## Standalone configuration

See [`.env.example`](../.env.example) for secret guidance. Export overrides in your terminal; `.env` files are not loaded automatically. Use absolute paths for overrides. Do not put a real Footage Review token in an environment file. Enter credentials in the masked UI form.

| Variable | Default | Purpose |
|---|---|---|
| `CLUSTER_DATA_DIR` | `backend/.data` resolved from the package | SQLite state, including JPEG crops and embeddings. |
| `CLUSTER_MODEL_DIR` | `backend/.models` resolved from the package | Verified YuNet and SFace weights. |
| `CLUSTER_ALLOWED_ORIGINS` | `http://localhost:3000,http://127.0.0.1:3000` | Comma-separated exact browser origins. |

The database file is `cluster-grouper.sqlite3` inside the state directory. It contains crop bytes; there is no separate crop-tree backup to collect.

Native mode supplies the library's absolute `Clustering` data directory through its private bootstrap and uses repository `backend/.models`. These standalone environment overrides do not configure native managed storage or credentials.

The browser connects through the Next.js API proxy. The default UI origin is exactly `http://localhost:3000`; `http://127.0.0.1:3000` is also a distinct origin. The backend's allowed-origin configuration must match the address you use. Footage Review's browser-origin setting can be blank because Python is its client.

## Manual browser review operation

1. Start the Footage Review API and connect using the current token.
2. Export a named review workspace and wait for successful completion.
3. Run clustering after model readiness is confirmed.
4. Review membership, names, and notes; approve intended groups.
5. Prepare and inspect the immutable import payload.
6. Submit explicitly and read its saved result.
7. Inspect the imported group and clips in Footage Review.

Pause or cancel jobs through the UI. Control takes effect at worker checkpoints rather than interrupting a database write or model call midway. Never treat counters alone as evidence that an export or import completed.

## Recover interrupted work

| Condition | Action |
|---|---|
| Backend restarted | Native: reopen/resume the saved run; service connection is automatic. Browser: establish the local session and reconnect only for upstream operations. Interrupted jobs remain paused until explicitly resumed. |
| Native tool environment missing | Check the repository folder in Settings; run the native setup/model commands above. |
| Export snapshot expired / 410 | Keep the incomplete workspace for reference; create a fresh export; verify IDs and reconcile decisions. |
| Models unavailable or hash mismatch | Rerun `make models`; inspect the reported failure. No fabricated embedding fallback is used. |
| Unusable crop | Inspect its status and source clip. Keep it visible for manual review rather than assuming a new person. |
| Footage Review 401 | Reconnect with the token from the currently running API listener. |
| Revision or library conflict / 409 | Export current state and reconcile. Do not change the saved request's revision blindly. |
| Import timed out / result uncertain | Retry the same saved immutable import after checking the connection; retain its UUID and payload. |
| Footage Review save error / 503 | Resolve the reported source-app problem, then retry the same saved import if its outcome is uncertain. |
| Disk or database error | Stop processing, inspect free space and permissions, preserve state, and restore from a known backup only after review. |

## Backups and restore

The local state directory contains sensitive review data, including crops, embeddings, labels, jobs and saved requests. Native state is the library's entire `Clustering` directory, including `NativeRun.json`; standalone state defaults to `backend/.data`. Stop its owning backend before copying the complete directory so SQLite/WAL and receipts remain consistent. Record the application revision and retain a private backup before a migration or repair. Do not copy a running SQLite database file by itself.

To restore, stop the owning services, keep current state as a separate recovery copy and restore the complete chosen backup. Native startup migrates its supplied directory; standalone `make migrate` uses its configured data directory. Inspect workspace/job/import state before resuming or submitting. A backup may be older than Footage Review's current revision; restoration does not authorize bypassing conflicts.

## Retention and local data retirement

Choose a retention period for the review purpose. After stopping the app and confirming no active job or unresolved import needs the data, retire the intended local state through your normal file-management process. Verify the selected path and preserve any required review receipt first. This action is deliberately not automatic. Browser downloads, backups, model files, and Footage Review's source library have separate lifecycles. The app never deletes source footage.

## Monitoring and incident response

Use visible job state and errors. Standalone terminal logs contain structured operational events; managed stdout is reserved for readiness and stderr for fixed, redacted failures. Avoid sharing full state directories or payloads in support reports. Never include tokens, crops or embeddings. If a token is disclosed, stop and restart Footage Review's API to rotate it, then reconnect the client. If local review data is disclosed, stop unintended sharing, preserve relevant evidence, assess affected records and follow the operator's incident process.

## Validation and rollback

Run `make check`, `make build`, and `make ui-test` before accepting code changes. `make audit` checks dependencies against current advisories. Keep a state backup before schema changes. Code rollback alone cannot safely undo a schema migration; restore a coherent backup and compatible code after reviewing any newer local work. No automatic destructive rollback or database reset is provided.

The npm manifest and lockfile are in `frontend/`. Use `npm --prefix frontend audit` from the repository root, or the canonical Make targets. An unscoped npm command can walk up to a separate parent project; an audit result containing unrelated MCP servers or other tooling must first be checked with `npm prefix`. Do not apply this application's dependency maintenance to that separate project.
