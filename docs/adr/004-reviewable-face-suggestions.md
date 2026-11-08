# ADR-004: Local face embeddings produce unapproved suggestions

Date: 2026-11-08
Status: Accepted

## Context

The source API exports detector crops and accepts human-reviewed labels. It does not infer identities. Similarity models can make false associations, especially in low-resolution footage.

## Decision

Use pinned, checksum-verified OpenCV Zoo YuNet and SFace models locally. Detect landmarks, align crops, cache normalized embeddings, and form deterministic greedy cosine suggestions in which every pair meets the threshold. This is not a globally optimal agglomerative algorithm. Keep unusable crops visible. Require human approval before a group enters a prepared import; require a separate submission action.

## Alternatives considered

- Automatic assignment and import: skips the review contract and can persist incorrect associations.
- Pixel or perceptual-hash grouping: does not provide a face-embedding comparison and can cluster background/image characteristics.
- External face-recognition API: introduces a data-transfer dependency unnecessary for the local workflow.

## Consequences

Model files are an explicit setup download. Thresholds are similarity settings, not calibrated identity probabilities. Synthetic protocol tests do not validate real-footage accuracy.

## References

- [OpenCV Zoo](https://github.com/opencv/opencv_zoo)
- [DPIA-lite](../dpia-lite.md)
