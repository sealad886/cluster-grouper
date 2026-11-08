# Changelog

## 0.1.0 — 2026-11-08

Initial versioned source release of Cluster Grouper.

- Export Footage Review detections and propose local face groups using verified YuNet and SFace models.
- Review crops, correct membership, approve groups, and explicitly submit immutable import requests with safe retries.
- Persist local work and support pause, resume, cancel, and recovery after interruption.
- Provide a browser interface and a native Footage Review integration patch with one-click managed services, progress, review, and organized Settings.
- Configure a shared product version, release metadata checks, and opt-in release PR automation. Publication remains unconfigured.
- License the project under Apache License 2.0.

Footage Review's native bundle has its own version, 1.3.0 build 4. It is separate from this product's `0.1.0` source release. See the [validation record](docs/validation.md) for tested behavior, the observed initial native startup timeout, and remaining real-footage acceptance work.
