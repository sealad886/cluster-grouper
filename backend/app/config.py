"""Configuration resolves independently of the process working directory."""

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent


def application_version() -> str:
    """Read the source-checkout application's canonical release version."""
    with (BACKEND_ROOT / "pyproject.toml").open("rb") as manifest:
        version = tomllib.load(manifest)["project"]["version"]
    if not isinstance(version, str) or not version:
        raise ValueError("The project's application version must be a nonempty string.")
    return version


@dataclass
class Settings:
    # Managed/native bootstrap exists only in memory and is never environment-configurable.
    managed_bootstrap_token: str | None = field(default=None, repr=False)
    data_dir: Path = field(
        default_factory=lambda: Path(os.getenv("CLUSTER_DATA_DIR", str(BACKEND_ROOT / ".data")))
    )
    model_dir: Path = field(
        default_factory=lambda: Path(os.getenv("CLUSTER_MODEL_DIR", str(BACKEND_ROOT / ".models")))
    )
    allowed_origins: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            os.getenv(
                "CLUSTER_ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
            ).split(",")
        )
    )

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.data_dir.resolve() / 'cluster-grouper.sqlite3'}"
