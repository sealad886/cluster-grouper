# Native Footage Review integration

Target: Footage Review **1.3.0, build 4**, using the existing Footage Review API v1 and Cluster Grouper local API. Native source and build script: `/Users/andrew/zRepos/videorebuild/test-results/face-appearances-2026-05-24_26/review-app`. Build output: `dist/Footage Review 1.3.0.app`. Reproducible application files are described in the [native delivery guide](../integrations/footage-review/README.md). Artifact, GUI and operator acceptance evidence is recorded separately in [validation.md](validation.md).

## Operator workflow

**Cluster Faces** starts or reuses Footage Review's authenticated integration API, launches a dedicated Python backend from the configured repository, connects without copying credentials, exports existing detections, and starts local similarity clustering. The native coordinator sequences the same export, job, review and immutable-import endpoints as the browser client. It does not scan footage, duplicate the Python worker, or automatically import a group.

Settings has three native tabs:

| Tab | Controls |
|---|---|
| General | Library location and Finder reveal; local processing information. |
| Clustering | Repository folder and setup check; exact date/source/camera scope; detected and ungrouped counts; cosine threshold; minimum group size; model and owned-service status. |
| Integrations | Footage Review API port and browser origin; start/stop/copy controls; import summary. |

Defaults are repository `~/zzApps/cluster-grouper`, API port `8765`, blank browser origin, cosine threshold `0.55`, minimum group size `2`, and all scope values. Port accepts 1024–65535, similarity 0–1, and minimum size 2–100. Settings persist in UserDefaults. The existing `review.api.port` string/integer value is backed up and migrated once to `review.settings.apiPort`; API tokens are not persisted.

Blank scope values mean all values. Nonblank date, source and camera values match displayed clip metadata exactly. Scope is independent of the main window's selection and filters. New runs capture their scope, threshold and minimum size; changing Settings does not rewrite a saved run. **Start New Clustering Run** applies changed settings after the current run is finished or cancelled.

One export supports at most **50,000 appearances**. Existing reviewed/manual memberships are excluded from new suggestions. The distinct upstream import limits remain **1–100 groups, 10,000 total assignments and 2 MiB per request**. These limits do not cap local comparison at 10,000 crops.

Native progress reports phases and counters and supports pause, resume and cancel at worker checkpoints. Review shows original crops matched by opaque appearance IDs. Saving a reviewed group stores its edited name, note and complete membership locally. Preparing an import shows the saved request; submission or uncertain-result retry is a separate explicit action. Starting clustering does not authorize automatic imports.

## Managed process protocol

Launch the absolute `backend/.venv/bin/python -m app.managed` executable with `backend/` as its working directory, without a shell. The parent sends one JSON line of at most **8,192 bytes** to stdin, then keeps that pipe open:

```json
{"protocol":1,"instance_id":"<UUID>","bootstrap_token":"<random secret>","data_dir":"<library>/Clustering"}
```

The bootstrap token is a printable random secret of 32–256 characters. The instance ID is a UUID and the data directory is absolute. Neither this secret nor the Footage Review credential belongs in argv, environment variables, files or logs. Model files remain in the configured repository's `backend/.models`.

The child binds only `127.0.0.1` on an OS-assigned port. After migrations, listener startup and a real HTTP readiness probe complete, stdout emits exactly one line:

```json
{"protocol":1,"instance_id":"<same UUID>","endpoint":"http://127.0.0.1:<actual port>"}
```

The parent verifies the protocol, exact instance ID, loopback endpoint and its own running `Process`. Fixed, redacted operational errors may appear on stderr. A readiness line does not imply model readiness or job completion; those are read through `/api/status` and job state.

In managed mode, `POST /api/session` requires `Authorization: Bearer <bootstrap_token>`. Subsequent private data routes, including `/api/connect`, require the resulting operator cookie in one ephemeral native URLSession. The native coordinator sends the current Footage Review credential through the existing `/api/connect` JSON body after bootstrap. Browser origins are not allowed in managed mode. Standalone browser session behavior remains documented in [api.md](api.md).

## Ownership and recovery

The native app owns only its dedicated child. It does not adopt or stop a process listening on another port. Closing the parent stdin pipe is the graceful shutdown signal; parent exit also closes that pipe. The backend pauses unfinished durable jobs through its normal lifespan shutdown. Native quit defers termination for owned-child cleanup and uses bounded termination fallback when needed. Ending a clustering run does not stop a separately started Footage Review API listener.

SQLite state is stored in `<library>/Clustering/cluster-grouper.sqlite3`, including JPEGs, cached embeddings, jobs, groups and immutable imports. `NativeRun.json` stores non-secret workspace/job references and run settings. Opening the app restores that receipt without automatically starting services; resume and saved-result review are explicit operations. Expired export snapshots require a new export and reconciliation. Uncertain imports retain their original UUID and exact payload for safe replay.

Import/group response UUIDs are checked by UUID identity, accepting uppercase Swift representations. Local keys and saved bytes are preserved; appearance IDs are never case-normalized or interpreted as UUIDs.
