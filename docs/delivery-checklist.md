# Delivery checklist

This ledger records implementation and verification separately from artifact, runtime and operator acceptance.

- [x] Read supplied Footage Review 1.2 API v1 quick reference and define integration invariants.
- [x] Implement backend, browser UI, local setup, and required design/operations documentation.
- [x] Verify focused protocol tests, job recovery, lint, types, production build, and browser smoke flow.
- [x] Record actual validation results and bounded remaining issues in [validation.md](validation.md).
- [x] Replace deprecated dependency paths and verify clean setup and zero app-scoped audit findings.
- [x] Implement native Settings, one-click owned-backend startup, scope controls, saved-run recovery and explicit reviewed imports using canonical Python endpoints.
- [x] Verify 40 backend tests, including managed subprocess lifecycle, >10,000-crop workflow and UUID response identity; retain passing backend static/migration checks.
- [x] Verify nine native source tests, including the positive actual-model fixture pipeline, settings, service ownership and recovery.
- [x] Update native/browser API, operations and security documentation; retain eight frontend lint probes and three browser tests from the verified browser delivery.
- [x] Apply and independently verify the native source patch, exact hashes, originals backup and preservation of unrelated files.
- [x] Build and ad-hoc sign Footage Review 1.3.0 build 4; verify plist and strict code signature.
- [x] Verify signed-bundle Settings, one-click clustering, native reviewed import, service restart and quit cleanup with an isolated public-sample library.
- [x] Configure one Cluster Grouper release owner, gated proposal-only automation, canonical runtime version and manifest/lock drift checks; preserve Footage Review's separate version.
- [x] Verify 76 backend tests and existing frontend checks, Actionlint, actual Release Please selectors and native lock consistency in a disposable candidate.

## Acceptance evidence that remains separate

- Installed Footage Review export and reviewed import acceptance using the actual current token/library.
- Single first-start GUI backend timeout remains unexplained; subsequent run and restart passed. Investigate if repeated.
- Hosted release automation activation, initial Git history/remote, approved baseline and any publication require separate authorization and live verification.
- Real-footage crop suitability and clustering quality reviewed by the operator.
- Operator privacy purpose, retention, backup, and legal assessment.

Synthetic/public-sample tests do not satisfy operator-library accuracy or human acceptance. Read-only inventory does not prove a completed full-library clustering run. Source test results do not establish final artifact/runtime status. See [native delivery files](../integrations/footage-review/README.md) and [validation.md](validation.md) for current evidence; no public release or commit is implied by this checklist.
