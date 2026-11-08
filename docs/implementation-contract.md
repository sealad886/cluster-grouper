# Implementation contract

Local-only, single-operator tool. FastAPI/SQLAlchemy/Alembic SQLite backend on 127.0.0.1:8000; Next.js/TypeScript frontend on localhost:3000 with /api rewrites. SQLite and a persistent single-process worker selected for a runnable local tool (no hosted service required). Tokens remain memory-only, session cookie HttpOnly/SameSite strict; local origin and host checks. No write to Footage Review during development without separate explicit user authorization.

## Shared browser API

JSON snake_case. Error responses: `{detail: {code: string, message: string}}`. Cookies authorize local operations after connect. Credentials never returned.

- `POST /api/session`: create local operator session cookie after strict local origin/host validation; permits offline review of persisted workspaces without a Footage Review token.
- `GET /api/status`: `{connected:boolean,session_active:boolean,library_id:string|null,revision:number|null,models_ready:boolean,model_message:string}`; unauthenticated, no private metadata when disconnected.
- `POST /api/connect` `{endpoint,token}` -> status, sets session cookie. Only literal http loopback endpoints permitted, no redirects. Verify health and groups with Bearer on each request. Token stays in memory.
- `POST /api/disconnect` -> `{ok:true}`, clears credentials.
- `GET /api/workspaces` -> array of `{id,name,library_id,base_revision,appearance_count,created_at}`.
- `POST /api/exports` `{name,date?:string,source?:string,camera?:string}` -> `{workspace_id,job_id}`. Background export: save groups first, fetch all pages; preserve IDs and metadata. Only mark complete on consistent library/revision/snapshot and null cursor. Store crops locally. Never silently restart expired snapshots or reuse partial exports for import.
- `GET /api/workspaces/{id}` -> `{id,name,library_id,base_revision,appearance_count,created_at,export_complete:boolean,appearances:Appearance[],groups:Group[],jobs:Job[],imports:Import[]}`.
- `GET /api/workspaces/{id}/appearances/{appearance_id}/image` -> JPEG with no-store. API returns safe local image URLs in Appearance.
- `POST /api/workspaces/{id}/cluster` `{threshold:number,min_cluster_size:number}` -> `{job_id}`. Deterministic greedy all-pairs cosine clustering over local YuNet-aligned SFace embeddings: every pair in a suggested cluster must meet threshold, preventing similarity chains (not a claim of globally optimal agglomeration). Threshold is similarity, 0-1 (default .55). Never auto-approve. Unusable crops get explicit errors. Cache per-crop embeddings. Preserve existing reviewed/manual groups; replace only prior unreviewed suggestions if needed.
- `GET /api/jobs/{id}` -> Job.
- `POST /api/jobs/{id}/control` `{action:'pause'|'resume'|'cancel'}` -> Job. Durable checkpoints. Restart leaves interrupted jobs paused for explicit resume (export may report snapshot expiry).
- `POST /api/workspaces/{id}/groups` `{name,note,appearance_ids,reviewed}` -> Group; generate UUID.
- `PATCH /api/workspaces/{id}/groups/{id}` `{name?,note?,appearance_ids?,reviewed?}` -> Group. Membership replaces full list, retained off-filter memberships must stay intact. Any substantive edit invalidates review unless explicitly reviewed in same request.
- `DELETE /api/workspaces/{id}/groups/{id}` -> `{ok:true}`. Discard local new groups only; never delete upstream existing groups.
- `POST /api/workspaces/{id}/imports` `{reviewer?:string}` -> Import; prepare immutable request from reviewed dirty groups only, validate PDF bounds and exact original library/revision. Requires completed export and fresh connection to same library. Save payload before posting. No implicit submission.
- `GET /api/workspaces/{id}/imports/{id}` -> Import (includes payload; downloadable through browser).
- `POST /api/workspaces/{id}/imports/{id}/submit` -> Import; Bearer, application/json, exact saved bytes. Manual submit/retry only; no automatic revision rebasing, replay after uncertain save uses same import_id and body. On 409 preserve draft, explain reconciliation; fresh export creates new workspace.

Appearance: `{id,clip_id,source,camera,date,clock,seconds,confidence,group_ids:string[],image_url:string,embedding_status:'pending'|'ready'|'unusable',embedding_error:string|null}`. Strings for unknown source/date/clock may be empty. Confidence is detection confidence.

Group: `{id,name,note,appearance_ids:string[],origin:'existing'|'suggested'|'manual',reviewed:boolean,dirty:boolean,similarity:number|null}`. Existing complete memberships include appearances outside filters.

Job: `{id,workspace_id,kind:'export'|'cluster',status:'queued'|'running'|'paused'|'cancelled'|'completed'|'failed',phase:string,completed:number,total:number,error:string|null}`.

Import: `{id,status:'prepared'|'submitted'|'uncertain'|'rejected',payload:object,response:object|null,error:string|null,created_at:string}`.

## Verification and model setup

Real API is not assumed available. Implement strict synthetic HTTP contract fixture/tests, including short nonterminal page, cursor-only later pages, Bearer on all data requests, 410, wrong library/revision, original full memberships, limits, atomic immutable retry. No fabricated accuracy claim. Models come from pinned OpenCV Zoo YuNet/SFace URLs and SHA256; install by documented script. Unit tests may use injected vectors; include actual local model smoke if models can be downloaded. Model readiness must reflect actual files/checksums, never a fake embedding fallback. A downloadable synthetic demo may be used only when clearly labelled; don't persist real biometric data as seed.

## Ownership

Backend specialist owns backend/ and backend tests. Frontend specialist owns frontend/. Documentation specialist owns README.md, docs except this file, .env.example, Makefile, scripts/, .github/. Root coordinates integration and independent verification. Preserve PDF and .DS_Store (ignore .DS_Store). No commits/pushes/releases without explicit authorization; no worktrees.
