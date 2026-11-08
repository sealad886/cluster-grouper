# Cluster Grouper

Licensed under the [Apache License 2.0](LICENSE).

Cluster Grouper turns face appearances exported by Footage Review into local similarity suggestions that you inspect, label, and return as reviewed groups. Footage Review 1.3.0 (build 4) provides native controls for this workflow. An optional browser interface uses the same backend. Crops, embeddings, review work, and saved import requests stay on your Mac.

## Use from Footage Review

Prepare this repository's Python environment and models once. From this folder, with [uv](https://docs.astral.sh/uv/) installed:

```bash
uv sync --directory backend --python 3.13 --locked --extra dev
make models
```

Then open a library with detected appearances in Footage Review 1.3.0. Clustering uses those existing detections:

1. Open **Settings → Clustering** and select this repository as the tool folder. Check the environment status; model integrity is verified when the backend starts.
2. Choose the appearance scope: exact date, source and camera values, or leave each at **All**. These settings are independent of the main window's filters and selection.
3. Click **Cluster Faces**. Footage Review starts or reuses its authenticated integration API, launches its own Python backend, connects without token copying, exports the chosen detections, and starts local clustering.
4. Use **Pause**, **Resume** or **Cancel** in the native progress panel. **Review Suggestions** opens the crop review interface.
5. Inspect membership, edit names and notes, and choose **Save Reviewed Group**. **Prepare Import** opens an immutable request preview; **Import Reviewed Groups** submits it only after your explicit action.

The native workflow needs no Node.js server or browser process. **Settings → General** shows the library location; **Settings → Integrations** retains manual API start/stop, origin and copy controls. The native source and build script live in the [Footage Review project](</Users/andrew/zRepos/videorebuild/test-results/face-appearances-2026-05-24_26/review-app>); its 1.3.0 bundle path is `dist/Footage Review 1.3.0.app`. The [native delivery files](integrations/footage-review/README.md) describe reproducible application of the integration.

Completed results and interrupted runs persist under the library's `Clustering` directory. A saved run keeps its original scope and settings. To apply changed scope or thresholds, use **Start New Clustering Run** after finishing or cancelling the current run. Reopening saved results does not rescan footage or automatically import groups. See the [native interface contract](docs/native-integration-contract.md) and [validation record](docs/validation.md) for implementation details and acceptance status.

## Optional browser interface

You need [uv](https://docs.astral.sh/uv/), Node.js 22.12 or newer, and npm. Setup selects Python 3.13 in the project's own environment; uv can download that interpreter if needed. The backend manifest supports Python 3.11–3.13. From this folder:

```bash
make setup
make models
make run
```

`make run` builds the current browser application, then starts its production server and the local API. Open [Cluster Grouper](http://localhost:3000) when startup finishes. Keep the terminal open; press Control-C to stop both services. `make status` shows which local services are reachable. The first setup downloads packages; `make models` downloads checksum-verified YuNet and SFace model files from OpenCV Zoo. Inference then runs locally without a model service.

### Connect manually

1. In Footage Review 1.3, open **Settings → Integrations**. In 1.2, use the **Integrations** toolbar control.
2. Choose its API port, usually `8765`, then click **Start API**.
3. Copy its endpoint and current access token into Cluster Grouper's connection form. The usual endpoint is `http://127.0.0.1:8765`.
4. Create an export. Optional date, source, and camera filters must exactly match Footage Review metadata.
5. Run clustering, inspect the suggested groups, correct membership, add names and notes, and mark the groups you have reviewed.
6. Prepare the import. Inspect or download the saved request, then explicitly submit it.
7. Open the returned group in Footage Review and inspect its appearances and source clips.

Cluster Grouper's Python backend calls Footage Review. The browser does not call it directly, so you can leave Footage Review's **Browser origin** blank for this client. The endpoint must be an HTTP loopback address on the same Mac. Restarting Footage Review's API creates a new token; reconnect with that token. Tokens are kept in backend memory and are not saved in the database or browser storage.

## Review behavior

- A detection is an **appearance**, not a person. Detection confidence and face-similarity scores describe different things.
- The default cosine threshold is `0.55`. A higher value makes suggestions more restrictive. This is a review setting, not a measured probability that two appearances show the same person.
- YuNet locates landmarks within each crop; SFace creates a local embedding. Crops that cannot produce a usable embedding remain visible with an explanation. There is no synthetic embedding fallback.
- Clustering proposes groups. Only groups you review and approve enter a prepared import.
- A local export supports up to **50,000 appearances**. Comparison is not limited to 10,000 crops. Each upstream import separately allows **100 groups, 10,000 assignments and 2 MiB**; large reviews must respect those request bounds.
- Existing groups retain their full membership, including appearances outside your export filters. The Footage Review API replaces each submitted group's complete membership, so removing an appearance is a deliberate edit.
- Jobs expose progress, pause, resume, and cancel. A partial export cannot be imported. After a restart, interrupted work requires explicit resume.
- A saved import is immutable. If a response is lost, retry that same saved request. A revision conflict requires a fresh export and reconciliation; the app does not silently change the revision.
- Import and group UUID responses are compared by UUID identity, so Swift's uppercase representation is accepted without changing saved request bytes. Appearance IDs remain opaque and unchanged.

## Try the API workflow with synthetic data

In a second terminal, run:

```bash
make demo
```

Connect to `http://127.0.0.1:8787` with the token `synthetic`. Its generated geometric JPEGs exercise API export and manual review. They do not measure face-recognition accuracy and may be marked unusable by the face model. This server is separate from your real Footage Review library.

## Development and verification

```bash
make check
make build
make ui-test
make audit
```

Release configuration uses one shared Cluster Grouper version, with a reviewed Release Please proposal workflow. `make release-check` validates version ownership and manifest/lock consistency, and is included in `make check`. The proposal workflow is disabled until its hosted prerequisites are deliberately enabled; publication is unconfigured. See the [release policy](docs/RELEASING.md) for the version-source map, first-release handling, approval boundaries and recovery.

`make check` runs backend lint, types, and tests plus frontend lint, eight lint regression probes, and types. `make ui-test` runs the browser smoke suite; install its Chromium runtime with `npm --prefix frontend exec -- playwright install chromium` first. Audit commands need network access to vulnerability databases.

The npm project lives in `frontend/`. From this repository root, use `make audit` or `npm --prefix frontend audit`. Plain `npm audit` searches parent directories for a package, so it can audit a separate home-directory project. The Makefile and CI explicitly select this application's directory. Review dependency updates through its manifest and lockfile, then run the checks above.

Frontend linting uses Oxlint's native React, Next.js, TypeScript, and accessibility rules. The backend uses HTTPX2 for its API client and treats test warnings as failures. See the [dependency maintenance decision](docs/adr/005-maintained-dependencies.md) for the replacement rationale and supported-tool constraints.

For frontend development with hot reload, run `npm --prefix frontend run dev` while the local backend is running. Normal use through `make run` serves the production build.

The [API guide](docs/api.md) records the exact pagination, revision, limit, and retry rules from [Footage_Review_API_Quick_Reference.pdf](Footage_Review_API_Quick_Reference.pdf). The [runbook](docs/runbook.md) explains startup, recovery, backups, and local data handling. [Architecture](docs/architecture.md), [data model](docs/data-model.md), [security](docs/security.md), [privacy assessment](docs/dpia-lite.md), and [control mapping](docs/compliance.md) describe the implementation and its limits.

## Scope and acceptance

This is a single-operator local application. It has no remote hosting, shared-user accounts, or cloud face processing. It does not scan footage or change source videos. Footage Review remains the authority for saved groups.

Automated tests and synthetic API fixtures establish the tested protocol behavior. They do not establish recognition accuracy on your footage or operator acceptance of the installed native app. Review quality depends on crop resolution, pose, lighting, model behavior, and your decisions. See the [validation record](docs/validation.md) for actual results and the [delivery checklist](docs/delivery-checklist.md) for evidence still required. The application-scoped dependency audits reported no known vulnerabilities on 8 November 2026; rerun `make audit` as advisories change.
