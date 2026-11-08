# API guide

The integration target is **Footage Review API v1**, described by the Footage Review 1.2 [quick reference](../Footage_Review_API_Quick_Reference.pdf), dated 8 November 2026, and used by the native 1.3 integration. Cluster Grouper exposes a separate local API for both native and browser clients. These APIs have different paths and authentication.

## Footage Review API

The Python backend connects to an HTTP loopback endpoint such as `http://127.0.0.1:8765`. Every data request sends `Authorization: Bearer <current token>`. Redirects and non-loopback endpoints are rejected. The token stays in backend memory.

| Method | Path | Purpose |
|---|---|---|
| GET | `/v1/health` | Read availability, `library_id`, and revision. |
| GET | `/v1/groups` | Read group items and the reviewed library revision. |
| GET | `/v1/appearances` | Export metadata and base64 JPEG crops using a snapshot cursor. |
| POST | `/v1/group-imports` | Atomically replace the supplied groups with reviewed names, notes, and full membership. |

The browser uses Cluster Grouper's same-origin proxy rather than contacting Footage Review directly. Its configured browser origin can be blank for this server client. A direct browser integration would need its exact scheme, host, and port configured and would still need Bearer authentication.

### Export contract

Read `/v1/groups` first and retain its `library_id`, `revision`, and complete group items. Request the first appearance page using optional exact-match `date`, `source`, and `camera` filters plus `limit`. Dates use `YYYY-MM-DD`; parameters are URL-encoded and are never repeated.

An appearance page contains `library_id`, `revision`, `snapshot_id`, `total`, `items`, and `next_cursor`. Each item retains its original `id`, `clip_id`, metadata, `seconds`, detector `confidence`, `group_ids`, and an `image` with `mime_type: image/jpeg` and base64 JPEG data.

Continue until `next_cursor` is `null`, even if a page is shorter than the requested limit. Later requests send the opaque cursor without reconstructing or altering it and omit the original filters. The client verifies that all pages match the workspace's library, revision, and snapshot. It does not treat a partial export as complete.

`total` counts appearances, not unique people. `confidence` is detection confidence. Date and clock are clip metadata and may be derived from filenames.

### Import contract

```json
{
  "import_id": "00000000-0000-4000-8000-000000000001",
  "library_id": "00000000-0000-4000-8000-000000000002",
  "base_revision": 7,
  "reviewer": "Local reviewer",
  "groups": [{
    "id": "00000000-0000-4000-8000-000000000003",
    "name": "Reviewed group",
    "note": "Membership inspected locally.",
    "appearance_ids": ["original-appearance-id"]
  }]
}
```

These are synthetic identifiers, not a usable request for your library. New group IDs and import IDs are UUIDs. Existing group UUIDs and all appearance IDs are preserved from the export. The request uses `Content-Type: application/json`.

Every supplied group replaces its name, note, and **complete membership**. An empty membership clears that group. Absent groups remain unchanged. An appearance can belong to several groups. Omitting a note clears the group's note; Cluster Grouper sends stored notes explicitly.

The API saves the whole import atomically or rejects all of it. A successful response contains `import_id`, `revision`, `current_revision`, `group_ids`, `appearance_count`, and `replayed`. The last count is the number of distinct appearances across submitted groups. Import revision and current library revision can differ on a replay.

Cluster Grouper saves the serialized request before submitting it. A lost response or uncertain save is retried with the same `import_id` and unchanged bytes. A deliberate edit needs a newly prepared import. A revision conflict requires fresh group state and reconciliation; changing `base_revision` alone is not reconciliation.

Response import/group UUIDs are compared as UUID values, accepting uppercase Swift formatting for a lowercase submitted UUID. This validation never rewrites a saved request or local group key. Appearance IDs remain opaque, case-sensitive strings. Different or malformed response UUIDs leave the import uncertain rather than reporting a confirmed save.

### Limits

| Item | Footage Review v1 bound |
|---|---|
| Page limit | Default 20; accepted range 1–50. |
| Export page | At most 8 MiB. |
| JPEG | At most 512 KiB. |
| Snapshots | Up to 30 minutes; at most four retained; a fifth evicts the oldest. Restart invalidates cursors. |
| Import request | At most 2 MiB, 1–100 groups, and 10,000 total assignments. |
| Group name | Trimmed length 1–120 characters; names must be unique. |
| Note / reviewer | At most 4,000 / 200 characters. |
| Server deadline | Ten seconds. |

### Error handling

Upstream errors contain both `code` and `message`. Keep the rejected saved request and read the code before editing.

| Result | Recovery |
|---|---|
| Cannot connect | Keep Footage Review open, start its API, and check the endpoint/port. |
| 400 | Correct query values, JSON, UUIDs, or field limits; do not repeat keys. |
| 401 | Reconnect with the token from the current API session. |
| 403 | For direct browser clients, match the configured exact origin and allowed headers. |
| 409 | Reconcile wrong-library, changed-revision, duplicate-name, or reused-import-ID conflicts. |
| 410 | Start a fresh export. Preserve review decisions separately and verify IDs before applying them to new state. |
| 413 | Reduce page size or the prepared import size. |
| 415 | Use JSON content type. |
| 422 | Refresh unknown appearance IDs or inspect missing/invalid crops in Footage Review. |
| 503 | Let restoration finish, resolve save failures, then retry the same saved request where the outcome is uncertain. |

## Cluster Grouper local API

In standalone mode FastAPI exposes [OpenAPI JSON](http://127.0.0.1:8000/openapi.json) and an [interactive reference](http://127.0.0.1:8000/docs). Browser requests use the Next.js `/api` proxy. Native managed mode uses a dedicated dynamic loopback endpoint and the [bootstrap protocol](native-integration-contract.md); no frontend server is involved. Error envelopes use `{ "detail": { "code": "...", "message": "..." } }`.

| Method | Path | Request / behavior |
|---|---|---|
| GET | `/api/status` | Connection and model readiness; no credentials. |
| POST | `/api/session` | Creates the local operator cookie for offline review; managed mode additionally requires the bootstrap Bearer token. |
| POST | `/api/connect` | `{endpoint, token}`; validates upstream health/groups. Managed mode requires the operator cookie first. |
| POST | `/api/disconnect` | Clears upstream credentials while retaining the local operator session. |
| GET | `/api/workspaces` | Workspace summaries. |
| POST | `/api/exports` | `{name, date?, source?, camera?}`; returns workspace and export-job IDs. |
| GET | `/api/workspaces/{id}` | Appearances, groups, jobs, imports, and completion state. |
| GET | `/api/workspaces/{id}/appearances/{appearance_id}/image` | Authenticated local JPEG response with no-store caching. |
| POST | `/api/workspaces/{id}/cluster` | `{threshold, min_cluster_size}`; starts a suggestion job. |
| GET | `/api/jobs/{id}` | Durable phase, status, counters, and error. |
| POST | `/api/jobs/{id}/control` | `{action: "pause" | "resume" | "cancel"}`. |
| POST | `/api/workspaces/{id}/groups` | `{name, note, appearance_ids, reviewed}`; creates a local manual group UUID. |
| PATCH | `/api/workspaces/{id}/groups/{id}` | Edits group fields; membership supplied is complete membership. |
| DELETE | `/api/workspaces/{id}/groups/{id}` | Discards a local new group; cannot delete an upstream existing group. |
| POST | `/api/workspaces/{id}/imports` | `{reviewer?}`; prepares reviewed dirty groups and saves the immutable payload. |
| GET | `/api/workspaces/{id}/imports/{id}` | Saved payload, status, response, and error. |
| POST | `/api/workspaces/{id}/imports/{id}/submit` | Explicitly submits or retries the exact saved request. |

The local API has one operator policy. Private data routes require its session cookie. A completed export may contain up to 50,000 appearances; clustering has no separate 10,000-crop comparison cap. Native date/source/camera settings feed the same exact-match export fields. The upstream import bounds still apply independently.

Connecting does not authorize a background automatic write to Footage Review: preparing and submitting remain separate actions. See [security](security.md) for the local trust model and [runbook](runbook.md) for recovery.
