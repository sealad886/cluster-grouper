# Security design

## System and assets

Cluster Grouper processes exported face crops and local similarity embeddings on one Mac. Its assets are the Footage Review access token, managed-process bootstrap secret, local session, appearance metadata/crops, embeddings, review decisions, and immutable import requests. Native process launch and pipes, the optional browser, Python service, Footage Review API, filesystem, and package/model sources are distinct trust boundaries.

This is a local operator tool. It does not implement remote accounts, shared tenancy, OIDC, or internet deployment. The actual session gate replaces an insecure development JWT stub. Do not expose either service through a public bind, tunnel, or reverse proxy without a separate design and security review.

## Entry points

- Browser connection, export, review, job-control, and import endpoints.
- Native child bootstrap over stdin and one readiness record over stdout.
- Upstream JSON, opaque cursors, metadata, and base64 JPEG crops.
- Local state and model files.
- Dependency and model installation.

## STRIDE analysis

| Threat | Component | Mitigation | Residual risk |
|---|---|---|---|
| Spoofing | Native child / local browser / upstream API | Exact managed instance and endpoint validation; bootstrap Bearer before managed cookie creation; private routes require the cookie; upstream Bearer auth; standalone host/origin checks. | Another process running as the same OS user has access to local resources. |
| Tampering | Group update | Original IDs and reviewed revision retained; full membership validation; saved immutable import; upstream atomic save and replay protection. | A reviewer can approve an incorrect group; upstream changes require reconciliation. |
| Repudiation | Review and submit | Saved payload, status, import UUID, upstream response, and structured operational records. | Single operator identity is not independently attested; logs are not tamper-proof. |
| Information disclosure | Token, crops, embeddings | Memory-only token; masked input; no browser credential persistence; local processing; authenticated crop routes and no-store responses; no enabled remote telemetry. | Filesystem data is not application-encrypted; disk encryption and account security are operator controls. |
| Denial of service | Bootstrap / export / image decoding / clustering | 8 KiB bootstrap; 50,000-appearance export cap; API response/JPEG bounds; PDF import limits; checkpointed controls; owned-child EOF shutdown. | Large libraries consume local disk, memory and CPU; no full-library throughput guarantee is made. |
| Elevation of privilege | Network or local API | Loopback binds, local session policy, allowed origins/hosts, no redirects to arbitrary upstream targets. | This is not a sandbox against malicious local software. |

## Controls and operational duties

Use a private OS account and full-disk encryption. Keep the state directory out of shared folders and cloud-sync paths when you do not intend to share its contents. Backups contain crops, embeddings, notes, and prepared payloads and need the same protection. Delete browser downloads separately from application state when your retention period ends.

Never place a real Footage Review token in `.env`, command arguments, source, test fixtures, or support logs. The native coordinator transfers it directly to its owned backend after bootstrap. In browser mode use the masked connection form. Restarting Footage Review's API rotates its token. Disconnect or stop the relevant backend to discard its in-memory credentials.

Managed mode starts an absolute repository-local Python executable without a shell. Its bootstrap secret is sent through stdin, kept in memory and used only to establish the operator cookie in an ephemeral URLSession. It is never persisted with the native run receipt. Managed mode rejects browser origins. It owns a new dynamic loopback listener and never adopts or kills an unrelated process. Parent pipe EOF initiates graceful shutdown and pauses unfinished durable work. See the [native contract](native-integration-contract.md).

Use the reviewed, saved import when retrying an uncertain outcome. Do not manually edit its UUID or base revision to force acceptance. Keep a backup of review state before a schema migration or manual repair.

Model files are obtained from pinned OpenCV Zoo sources and checked against their SHA256 values. No substitute hash or unverified fallback is accepted. Normal inference uses local OpenCV CPU processing. A failed model setup leaves readiness false and must not be reported as successful clustering.

## Logging and observability

Standalone logs contain event names, safe job/import identifiers, state transitions, counters and sanitized errors. Managed mode reserves stdout for its single readiness record and emits only fixed, redacted operational errors on stderr; detailed job outcomes remain in authenticated state. Neither mode logs token values, authorization headers, crop bytes, embeddings or full import bodies. Saved payloads live in protected local state. Remote error reporting is not configured; adding it requires a reviewed data-flow decision.

## Verification and remaining limits

Synthetic protocol tests verify the tested authentication, pagination, validation, and replay behavior. They do not establish protection against every local attack, installed Footage Review acceptance, recognition accuracy, or regulatory compliance. See [risk register](risk-register.md), [control mapping](compliance.md), and [delivery checklist](delivery-checklist.md).
