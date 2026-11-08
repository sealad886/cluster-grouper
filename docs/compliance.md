# Control mapping

This document records implementation controls and operator duties. It is not a certification, legal opinion, ASVS attestation, or SOC 2 report. Review the actual processing purpose and deployment before using real data beyond development.

## GDPR considerations

The operator is responsible for determining applicability, lawful purpose, Article 6 basis, any Article 9 condition, notice, rights handling, and whether a formal DPIA is needed. Facial embeddings may be biometric data when used to identify people. Retention must be chosen for the purpose; local execution alone does not settle lawful use. See the [GDPR primary text](https://eur-lex.europa.eu/eli/reg/2016/679/oj/eng) and the project [DPIA-lite](dpia-lite.md).

| Theme | Implementation / operator evidence | Remaining duty |
|---|---|---|
| Minimization and purpose | Export filters; local processing; explicit approved import. | Select only the footage needed and avoid unrelated uses. |
| Transparency | Documented data flow and visible model suggestions. | Provide an appropriate notice for the actual context. |
| Access and portability | Original appearance IDs and downloadable prepared payloads. | Coordinate complete records with the source Footage Review library. |
| Rectification, restriction, objection | Manual group edits and controlled submission. | Resolve requests and stop processing where required. |
| Erasure and retention | Local state location and backup procedure documented. | Apply a retention schedule across crops, embeddings, exports, downloads, backups, and source systems. |
| Security | Session, origin/host policy, memory-only token, local binds, checksummed models. | Protect the OS account and disks; review permissions and incidents. |
| Transfers | No external inference service; local API integration. | Assess any sharing, synced folder, backup provider, or future telemetry service. |

## OWASP ASVS themes

The current [OWASP ASVS project](https://asvs.owasp.org/) publishes versioned requirements. This lightweight mapping uses topic names rather than claiming a particular verification level or reusing chapter numbers from a different version.

| Theme | Project control | Evidence / gap |
|---|---|---|
| Architecture and threat modeling | Local trust boundaries and STRIDE analysis. | [Architecture](architecture.md), [security](security.md). |
| Authentication | Footage Review Bearer token and local session. | Test same-machine credential flow; no remote account/MFA support. |
| Session management | HttpOnly SameSite session; credentials memory-only. | Reconnect after backend restart. |
| Access control | Single-operator session and workspace policy hooks. | No multi-tenant authorization claim. |
| Validation and encoding | Pydantic input validation; loopback endpoint policy; bounded JSON/JPEG/import values; React text rendering. | Tests must exercise malformed and conflicting input. |
| Errors and logging | Code/message errors, durable failed states, sanitized structured logs. | Local logs are not a central audit system. |
| Data protection | Local storage, protected crop responses, no enabled telemetry. | Disk encryption and retention are operational controls. |
| Communications | HTTP limited to loopback; direct upstream requests carry Bearer. | Remote TLS deployment is outside this app's scope. |
| Dependency integrity | Lockfiles, model hashes, CI dependency audit. | Network audit results change and need rerunning. |

## SOC 2-style operational themes

| Theme | Present controls | Limit |
|---|---|---|
| Security | Local session, endpoint policy, dependency scans. | No organizational access review or independent audit. |
| Availability | Health/status UI, durable jobs, restart recovery, backups. | Single Mac; no uptime SLA or high availability. |
| Confidentiality | Local inference, no saved token, no-store crops. | OS/disk protection and backup security required. |
| Processing integrity | Library/revision/snapshot checks, reviewed groups, immutable retries. | Human review and installed API acceptance remain necessary. |
| Privacy | Data-flow documentation and retention guidance. | Operator owns legal assessment and rights workflow. |

HIPAA, PCI DSS, ISO 27001 certification, and EU MDR are not implementation targets for this local footage-review tool. It handles no payment cards and makes no medical claim. A new regulated purpose requires a separate assessment.
