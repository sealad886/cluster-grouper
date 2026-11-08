"""Local feature extraction and conservative all-pairs similarity partitioning."""

import base64
import binascii
import io
from collections.abc import Callable
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image, UnidentifiedImageError

from app.errors import IntegrationError
from app.models_setup import models_ready


def decode_jpeg(encoded: str) -> bytes:
    try:
        data = base64.b64decode(encoded, validate=True)
        if len(data) > 512 * 1024:
            raise ValueError("Crop exceeds 512 KiB")
        with Image.open(io.BytesIO(data)) as image:
            if image.format != "JPEG" or max(image.size) > 4096 or min(image.size) < 8:
                raise ValueError("Invalid JPEG dimensions or format")
            image.verify()
        with Image.open(io.BytesIO(data)) as image:
            image.load()
        return data
    except (ValueError, binascii.Error, UnidentifiedImageError, OSError) as exc:
        raise IntegrationError(
            "invalid_crop", "Export contains a missing or invalid JPEG crop.", 422
        ) from exc


class FaceEngine:
    def __init__(self, directory: Path) -> None:
        ready, message = models_ready(directory)
        if not ready:
            raise IntegrationError("models_missing", message, 503)
        self.detector = cv2.FaceDetectorYN.create(
            str(directory / "face_detection_yunet_2023mar.onnx"), "", (320, 320), 0.8, 0.3, 5000
        )
        self.recognizer = cv2.FaceRecognizerSF.create(
            str(directory / "face_recognition_sface_2021dec.onnx"), ""
        )

    def embed(self, data: bytes) -> list[float]:
        image = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("Cannot decode crop")
        # A detection crop can be small; scale it for landmark detection, preserving aspect ratio.
        h, w = image.shape[:2]
        scale = max(1.0, 320.0 / max(h, w))
        if scale != 1:
            image = cv2.resize(image, (round(w * scale), round(h * scale)))
        self.detector.setInputSize((image.shape[1], image.shape[0]))
        _, faces = self.detector.detect(image)
        if faces is None or len(faces) == 0:
            raise ValueError("No usable face landmarks; review crop manually")
        if len(faces) != 1:
            raise ValueError("Multiple faces in crop; review manually")
        aligned = self.recognizer.alignCrop(image, faces[0])
        vector = self.recognizer.feature(aligned).reshape(-1).astype(np.float32)
        norm = float(np.linalg.norm(vector))
        if not np.isfinite(vector).all() or norm <= 0:
            raise ValueError("Invalid face embedding")
        return (vector / norm).tolist()


def complete_link_partition(
    embeddings: dict[str, list[float]],
    threshold: float,
    minimum: int,
    checkpoint: Callable[[int, int], None] | None = None,
) -> list[dict[str, Any]]:
    """Deterministic greedy complete-link partition, never transitive similarity chaining.

    Each added crop must satisfy threshold against EVERY existing member. This is a
    conservative partition, not a claim of optimal/global agglomerative clustering.
    Similarity records the minimum pair cosine in each suggested group.
    """
    keys = sorted(embeddings)
    if not keys:
        return []
    vectors = np.array([embeddings[key] for key in keys], dtype=np.float32)
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    if not np.isfinite(vectors).all() or np.any(norms == 0):
        raise ValueError("Embeddings must contain finite, nonzero vectors")
    vectors = vectors / norms
    groups: list[tuple[list[int], float]] = []
    for index in range(len(keys)):
        if checkpoint:
            checkpoint(index, len(keys))
        best = -1
        best_score = -2.0
        for group_index, (members, _) in enumerate(groups):
            score = float(np.min(vectors[members] @ vectors[index]))
            if score >= threshold and score > best_score:
                best, best_score = group_index, score
        if best == -1:
            groups.append(([index], 1.0))
        else:
            members, score = groups[best]
            members.append(index)
            groups[best] = (members, min(score, best_score))
    return [
        {"appearance_ids": [keys[i] for i in members], "similarity": round(score, 6)}
        for members, score in groups
        if len(members) >= minimum
    ]
