# Validation record

Date: 2026-11-08. Scope: this local backend/browser implementation, its release configuration, and the native Footage Review 1.3.0 build-4 integration source, using the supplied API v1 reference. Test libraries and imports described below use synthetic fixtures or the identified public sample. Read-only inventory of the operator's library is separate from write acceptance and clustering-quality evidence.

## Automated checks

| Check | Result | Evidence scope |
|---|---|---|
| Backend behavioral suite | 76 passed, zero warnings | Existing 40 protocol/job/managed tests, 35 release-metadata CLI regressions and one public runtime-version test; warnings are errors |
| Ruff lint and formatting | Passed | Backend source and tests |
| Mypy | Passed, 15 modules | Backend application types, including managed mode |
| Alembic schema drift check | Passed | Models agree with initial migration |
| Backend dependency audit | No known vulnerabilities reported | After upgrading Pillow to 13.0.0; advisory databases remain time-sensitive |
| Oxlint and TypeScript | Passed | Frontend source and generated API schemas; lint warnings are errors |
| Lint behavior regression probes | 8 passed | Invalid hooks, effects, accessibility, Next.js and TypeScript cases rejected; valid crop images accepted |
| Playwright regression suite | 3 passed | Review/import, offline membership preservation, terminal job feedback |
| Final production build | Passed | Next.js 16.4.5 with React/ReactDOM 19.3.1; explicit frontend build/tracing roots |
| Shell syntax | Passed during browser delivery | Launch/status scripts |
| Updated documentation links | Passed | 40 local links across the eight native-integration documentation files |
| Native source test suite | 9 passed | Three settings tests, three service tests, two recovery tests and one actual-model pipeline test |
| Native release artifact | Passed | Canonical build script; ad-hoc signed 1.3.0 build 4 bundle, plist validation and strict signature verification |
| Native GUI sample round trip | Passed | Automatic service startup, actual model suggestions, review, immutable preview, explicit import and original appearance IDs |
| Native GUI service lifecycle | Passed | Settings stop, restart/reopen saved results, app quit, owned child exit and API listener closure |
| Native source patch application | Passed | Independent fresh-apply, hash, backup, idempotence, changed-baseline refusal and unrelated-file preservation checks |
| Release metadata and workflows | Passed locally | `make release-check`, pinned upstream schema structure validation and Actionlint 1.7.12; hosted activation remains untested |
| Actual release-tool/native lock probe | Passed | Release Please 17.6.0 updated all five fields in a disposable candidate; uv/npm native lock commands left those generated files byte-identical |

## Release configuration verification

Cluster Grouper's backend and private frontend are one product unit with `backend/pyproject.toml` as canonical version source. Runtime OpenAPI metadata now reads that source independently of the working directory. At configuration time, `0.1.0` was an unreleased candidate and the tracking manifest was empty because the repository had no commits, tags or remote. The user subsequently authorized the initial commit and local `v0.1.0` tag; its tracking version is therefore initialized to `0.1.0` without bumping the application or lockfiles. Hosted and registry publication remain outside this local release. Footage Review's independent native version and source were not changed by this release-configuration task.

`make check` passed after configuration: 76 backend tests, Ruff, formatting, Mypy across 15 modules, frontend Oxlint, eight lint behavior probes and TypeScript. The new checker also passed with `--expect-version 0.1.0 --require-baseline-tag`. Its 35 CLI regressions cover mismatched mirrors, private-package identity, single-writer scope, invalid versions, initial state, and missing/unreachable/wrong-version tags. Disposable Git test fixtures disable global configuration, hooks and signing. No source-repository commit or tag was created.

The SHA-pinned Release Please action 5.0.0 bundles library 17.6.0. Its actual typed updaters were exercised against all five configured fields across four in-memory source files. This caught and corrected the uv JSONPath: the tagged TOML tree requires `@.name.value`, whereas `@.name` matched nothing. All unrelated uv/npm dependency entries remained unchanged.

A disposable source fixture then received those actual generated `0.2.0` values. `uv 0.13.7 lock --check --offline --python 3.13 --no-python-downloads` passed, as did `npm 12.2.0 --offline install --package-lock-only --ignore-scripts --no-audit --no-fund`. Native checks left all four generated files byte-identical. All 64 uv and 115 npm package records were compared; only the intended product version fields differed from the originals. Hashes confirmed all four canonical manifest/lock files remained unchanged. No app dependency was added, and the fixture installed no application environment or node_modules.

The proposal workflow is disabled unless its repository variable is deliberately enabled. It has a baseline-tag guard, scoped write permissions and `skip-github-release: true`, with no publisher/deploy commands. Actionlint and the pinned upstream configuration schema's structure validation passed locally. Schema format validation was not needed for the fixed upstream schema URL. Release Please engine probes and native tools were temporary validation installations; they were not added to app setup dependencies. Hosted release PR behavior, branch protection and publication have not been exercised or configured externally. See [RELEASING.md](RELEASING.md) for authority, recovery and the handoff to `verify-release`.

The initial frontend install reported eight moderate advisories while the online audit endpoint was unavailable. A subsequent online scan traced all eight to one minimatch advisory in the old lint dependency chain. After replacing that stack, a fresh online `npm --prefix frontend audit` returned zero vulnerabilities, including development dependencies. The new lockfile contains no deprecated package entries or forced version overrides. A clean install added 64 packages and completed without package warnings. See [ADR-005](adr/005-maintained-dependencies.md) for the maintenance rationale. Advisory results are time-sensitive; rerun `make audit`.

## Dependency maintenance verification

Canonical `make setup`, `make check`, `make audit`, and `make ui-test` passed after the updated lockfiles were installed. Setup emitted no deprecation warnings. The frontend now resolves 114 dependency entries instead of 422; the installed Mac package count dropped from 370 to 64. React/React DOM are 19.3.1, Playwright is 1.65.0, Oxlint is 1.92.0, and OpenAPI tooling is pinned at 7.13.0. TypeScript remains at compatible 5.9.3. The Node requirement is 22.12 or newer.

The backend uses HTTPX2 2.16.0 with HTTPCore2 2.16.0 and truststore 0.10.5. HTTPX and HTTPCore were removed from the manifest, lockfile and environment. All 31 tests passed with warnings treated as errors, including the previously warning-producing Starlette TestClient path. A separate actual loopback HTTP test exported all 12 synthetic appearances, submitted a synthetic import at revision 8, and replayed the identical saved request successfully. This client test used real sockets, separately from the browser tests' mocked API; no real Footage Review library was contacted.

The three browser regression tests passed with the Chromium runtime matched to Playwright 1.65.0. The eight new lint probes exercise behavior rather than configuration text. An independent review checked lint rule mappings and bounded differences, package compatibility, lockfile consistency, absence of deprecated entries/overrides, and preservation of the separate parent project's package files. Build and tracing roots are explicitly scoped to `frontend/`, so builds no longer infer a project from the parent lockfile.

During sandboxed verification, package caches were placed in a temporary writable directory. Tool-inherited unsupported npm proxy keys were removed only from verification child processes; standard proxy settings were retained. No warning suppression, forced peer resolutions, global configuration changes, or parent-project dependency updates were used. Browser tests emitted color-environment warnings from Playwright's `FORCE_COLOR` and the tool's `NO_COLOR`, not dependency deprecations.

## Independent contract and recovery review

A separate reviewer used temporary SQLite databases, synthetic vectors and an in-memory HTTP transport. The tested paths preserved Bearer authentication, cursor-only continuation after a short page, complete existing memberships outside export filters, immutable prepared payloads, original revisions, and same-ID byte-identical replay after a lost response and process restart. A newer replay `current_revision` did not rebase the saved request. Local edits made after preparation remained dirty and unreviewed when the older import succeeded.

Pause prevented a late feature commit; resume completed with unreviewed suggestions. Interrupted jobs became paused after restart, and cancelled jobs rejected resume. Host/origin checks and unauthenticated data access were exercised. Review found and corrected missing JSON headers on empty browser mutations and a frontend/backend minimum-group-size mismatch.

## Native integration and managed backend

The native integration source was applied to the canonical Footage Review project with hash-checked file application and a preserved local backup at `.integration-backups/20261108T204635Z`. All 22 changed paths match the delivered manifest; the historical 1.2 validation file remains unchanged. An independent reviewer verified the patch on a temporary baseline, including fresh application, preserved unrelated files, idempotence and refusal of a changed baseline.

Nine native source tests passed, including a positive pipeline using two appearances of the public face sample through the actual local model. Settings, service ownership and recovery tests are part of that count. The canonical build script then produced Footage Review 1.3.0, build 4, requiring macOS 26 or newer. Plist validation and `codesign --verify --deep --strict` passed. This is a local ad-hoc signature, not notarization or public distribution.

The signed bundle was launched with an isolated two-appearance public-sample library. Computer-use inspection verified the General, Clustering and Integrations Settings tabs, Command-comma, exact scope controls, model readiness and service status. A toolbar click started the native API and owned Python backend, exported both detections and generated one suggestion. Native approval enabled preparation; the saved request preview retained revision 0 and both original appearance IDs. Explicit import displayed "Import Accepted" and saved one native group. Reading the fixture's `Library.json` confirmed `public-fixture-1` and `public-fixture-2`. No operator-library clustering or import was performed.

The original default API port 8765 was occupied by the existing SpeechForge process. Settings now use port 18765, and that service was left untouched. The first GUI backend startup timed out after 20 seconds; its cause remains unproven. A retry launched and completed clustering in about three seconds. Settings stop and a subsequent restart successfully reopened the saved results. No speculative timeout change was made. Quitting the fixture app removed its exact owned Python child and API listener; the pre-existing Xcode debug app remained running. This first-start timeout remains an observed bounded reliability issue, despite subsequent successful runs.

The canonical `script/build_and_run.sh --verify` subsequently built and launched the bundle normally without fixture overrides. Process and file-lock readback confirmed the packaged app used `dist/Footage Review Library`, with no managed clustering child started. SHA-256 hashes of both original `Library.json` files (packaged and existing Xcode debug libraries) remained unchanged across this normal launch. The released executable's local SHA-256 is `4932fd635bb3a778db06888125c1d89c2cc3fe850e8b0724b22d26a3fc45ebca`; the app is ad-hoc signed and remains local.

Python subprocess tests launch an actual owned child on a dynamic loopback port with temporary data. They verify migration and HTTP readiness before announcement, missing/wrong bootstrap rejection, cookie-gated private routes, one stdout readiness record, redacted output, EOF shutdown, listener closure and retained paused state after restart. No existing port-8000 process is adopted or stopped.

The updated import regression accepts Swift's uppercase import/group UUID response for a lowercase submitted UUID, records a successful save and replays the same saved bytes. Local group keys and opaque appearance IDs remain unchanged. Different and malformed response UUIDs retain an uncertain result instead of producing a confirmed save or an uncaught parsing error.

A read-only inventory reported 39,399 detections in the operator's library. The obsolete 10,000-comparison guard was removed because that library fits the existing 50,000-appearance export limit. A regression completes a public clustering job with 10,001 cached synthetic appearances and an injected bounded partition, preserving unreviewed suggestions and avoiding feature extraction again. It verifies the capacity contract, not full-library algorithm throughput or grouping quality. The API's 100-group, 10,000-assignment and 2 MiB import limits remain unchanged.

## Actual model inference

Both OpenCV Zoo model files were downloaded from commit `48b10fa505aeb51fbd127fc60a5c660040e823b7` and checked against pinned SHA256 and sizes. OpenCV 4.14.0 loaded YuNet and SFace and processed a JPEG face crop from the public scikit-image v0.25.2 astronaut sample:

- Crop: 182 by 144 pixels.
- Embedding: 128 finite values, normalized to unit length.
- Original versus brightness-adjusted crop cosine: 0.996477.
- Blank crop: rejected for lack of usable face landmarks.

This proves that the actual model pipeline runs locally. It is not a multi-person accuracy benchmark or evidence about this operator's footage. The sample and temporary visual captures were not added to the repository.

Model references: [OpenCV's detection/recognition pipeline](https://docs.opencv.org/4.13.0/d0/dd4/tutorial_dnn_face.html), [pinned OpenCV Zoo source](https://github.com/opencv/opencv_zoo/tree/48b10fa505aeb51fbd127fc60a5c660040e823b7), and [public scikit-image sample](https://github.com/scikit-image/scikit-image/blob/v0.25.2/skimage/data/astronaut.png).

## Production HTTP and browser walkthrough

The launcher built the frontend and served it in production mode. Headless Chromium exercised the actual browser UI, Next.js proxy, local FastAPI process, SQLite state, and a separate synthetic Footage Review HTTP server on port 8787. This test used no route mocks between those processes.

The app exported all 12 fixture appearances through short pages. Actual local inference marked all geometric fixture drawings unusable. After restart, the browser opened the persisted workspace while disconnected. It then connected to the synthetic API, created a two-member manual group, approved it, prepared a saved request at base revision 7, inspected its exact appearance IDs, and explicitly submitted it. The synthetic API accepted it at revision 8. Disconnect retained local review access. The browser reported zero page errors. Desktop visual inspection and a 390-pixel mobile layout check passed, including no horizontal document overflow. Synthetic workspace data is labelled `Synthetic UI smoke (demo)` and is not a real library export.

The direct computer-use browser host was unavailable. Browser verification therefore used the application's Playwright tooling, including actual production pages and local HTTP services. This is automated UI evidence, not operator acceptance.

## Launch and shutdown

`make status` reported HTTP 200 from both local services and verified models ready. Control-C stopped both owned production PIDs; both were checked absent, and ports 3000 and 8000 could be rebound. The app can be launched again with `make run`. The synthetic API is a separate process used only for testing.

## Remaining acceptance

- Actual installed Footage Review export and reviewed-import acceptance with the operator's current token.
- Investigate the single first-start GUI backend timeout if it recurs; later startup and restart passed.
- Real-footage crop suitability, grouping precision/recall, and threshold selection by review.
- CI execution on GitHub; configuration exists, but no workflow was published or run there.
- Load testing and an independent comprehensive security/accessibility audit.

Cluster Grouper source and the user-authorized initial `v0.1.0` release remain local on `codex/facial-clustering`; no push, hosted deployment or public release is authorized by the local commit/tag operation. Native integration artifacts and their apply/verify procedure are described in the [delivery guide](../integrations/footage-review/README.md).
