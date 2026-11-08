# Footage Review native integration

`native-integration.patch` contains the SwiftPM source changes for Footage Review 1.3.0 (build 4). Its native UI starts the existing Footage Review API and an owned Cluster Grouper Python process, then exports detections and starts clustering. Settings use the standard macOS Settings window, with General, Clustering, and Integrations tabs. Review and import remain explicit actions.

The native source currently lives in an ignored output directory of VideoRebuild:

```text
/Users/andrew/zRepos/videorebuild/test-results/face-appearances-2026-05-24_26/review-app
```

This patch keeps the integration reviewable in Cluster Grouper without copying a second native application into this repository. `manifest.json` records SHA-256 hashes before and after each of the 22 changes, including removal of the obsolete Integration sheet. Unrelated files, historical validation, libraries, and existing app bundles are outside the patch.

## Apply and build

From the Cluster Grouper repository, run:

```bash
backend/.venv/bin/python integrations/footage-review/apply.py /path/to/review-app
cd /path/to/review-app
./script/build_and_run.sh
```

The helper refuses a changed source baseline, checks a dry run, and saves originals plus a hash receipt under `review-app/.integration-backups/<UTC timestamp>/` before applying. It recognizes an already-applied integration. If native source has changed independently, reconcile the patch against those changes instead of forcing it. Backups remain local and are not installed in the app bundle.

The canonical build script creates and ad-hoc signs `dist/Footage Review 1.3.0.app`. It refuses to overwrite that bundle while its process is running. macOS 26 or newer is required. If the development host cannot nest SwiftPM's package sandbox, use `FOOTAGE_REVIEW_DISABLE_PACKAGE_SANDBOX=1 ./script/build_and_run.sh`; this only changes the package build invocation.

## Native verification

`swift test` runs DTO, endpoint, and Settings checks. Managed-process recovery tests additionally require `CLUSTER_NATIVE_E2E_REPOSITORY` pointing at a prepared Cluster Grouper checkout. The actual-model round trip also requires `CLUSTER_NATIVE_E2E_ASSETS` with `crop-1.jpg`, `crop-2.jpg` (two crops of the same public sample face), and a valid `source.mp4`. These tests use temporary libraries and do not access the user's footage.

For isolated GUI verification, launch the signed bundle with `FOOTAGE_REVIEW_LIBRARY` pointing to an explicitly prepared test library and `FOOTAGE_REVIEW_SKIP_SEED=1`. Normal launch uses the existing adjacent Footage Review Library. See the [integration contract](../../docs/native-integration-contract.md) and [validation record](../../docs/validation.md) for behavior and measured evidence.
