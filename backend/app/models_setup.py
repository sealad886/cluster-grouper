"""Download pinned official OpenCV Zoo models, verifying exact SHA256 and size."""

import hashlib
import os
from pathlib import Path

import httpx2

from app.config import Settings

COMMIT = "48b10fa505aeb51fbd127fc60a5c660040e823b7"
MODELS = {
    "face_detection_yunet_2023mar.onnx": (
        "face_detection_yunet",
        "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4",
        232589,
    ),
    "face_recognition_sface_2021dec.onnx": (
        "face_recognition_sface",
        "0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79",
        38696353,
    ),
}


def models_ready(directory: Path) -> tuple[bool, str]:
    for filename, (_, expected_hash, expected_size) in MODELS.items():
        path = directory / filename
        if not path.is_file():
            return False, "Install local face models with make models."
        stat = path.stat()
        if stat.st_size != expected_size or file_hash(path) != expected_hash:
            return False, "A model failed integrity verification. Run make models to repair it."
    return True, "Verified YuNet + SFace models ready for local CPU processing."


def file_hash(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def main() -> None:
    directory = Settings().model_dir
    directory.mkdir(parents=True, exist_ok=True)
    with httpx2.Client(timeout=120, follow_redirects=True, trust_env=False) as client:
        for filename, (model, expected_hash, expected_size) in MODELS.items():
            target = directory / filename
            if target.is_file() and file_hash(target) == expected_hash:
                print(f"Verified {filename}")
                continue
            url = f"https://media.githubusercontent.com/media/opencv/opencv_zoo/{COMMIT}/models/{model}/{filename}"
            temporary = target.with_suffix(".download")
            try:
                digest = hashlib.sha256()
                size = 0
                with client.stream("GET", url) as response, temporary.open("wb") as output:
                    response.raise_for_status()
                    for chunk in response.iter_bytes():
                        size += len(chunk)
                        if size > expected_size:
                            raise ValueError("Model download exceeds pinned size")
                        digest.update(chunk)
                        output.write(chunk)
                    output.flush()
                    os.fsync(output.fileno())
                if size != expected_size or digest.hexdigest() != expected_hash:
                    raise ValueError(f"Integrity check failed for {filename}")
                temporary.replace(target)
                print(f"Installed and verified {filename}")
            finally:
                temporary.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
