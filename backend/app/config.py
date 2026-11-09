"""Runtime settings, read from environment variables with safe defaults.

Every path defaults to a location inside the project folder, so unzipping the project and
running ``start.bat`` / ``start.sh`` works without any configuration.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _env_path(name: str, default: Path) -> Path:
    value = os.environ.get(name)
    return Path(value).expanduser().resolve() if value else default


def _env_list(name: str, default: list[str]) -> list[str]:
    value = os.environ.get(name)
    if value is None:
        return default
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    """All tunable settings for the backend (override with CROPDOC_* environment variables)."""

    root: Path = PROJECT_ROOT
    model_dir: Path = field(
        default_factory=lambda: _env_path("CROPDOC_MODEL_DIR", PROJECT_ROOT / "models" / "active")
    )
    results_dir: Path = field(
        default_factory=lambda: _env_path("CROPDOC_RESULTS_DIR", PROJECT_ROOT / "results")
    )
    data_dir: Path = field(
        default_factory=lambda: _env_path("CROPDOC_DATA_DIR", PROJECT_ROOT / "data" / "app")
    )
    inbox_dir: Path = field(
        default_factory=lambda: _env_path("CROPDOC_INBOX_DIR", PROJECT_ROOT / "data" / "inbox")
    )
    frontend_dist: Path = field(
        default_factory=lambda: _env_path("CROPDOC_FRONTEND_DIST", PROJECT_ROOT / "frontend" / "dist")
    )
    diseases_file: Path = field(
        default_factory=lambda: _env_path(
            "CROPDOC_DISEASES_FILE", Path(__file__).parent / "data" / "diseases.json"
        )
    )
    max_upload_bytes: int = int(os.environ.get("CROPDOC_MAX_UPLOAD_MB", "5")) * 1024 * 1024
    max_image_pixels: int = int(os.environ.get("CROPDOC_MAX_IMAGE_PIXELS", str(40_000_000)))
    cors_origins: list[str] = field(
        default_factory=lambda: _env_list(
            "CROPDOC_CORS_ORIGINS", ["http://localhost:5173", "http://127.0.0.1:5173"]
        )
    )
    rate_limit_per_minute: int = int(os.environ.get("CROPDOC_RATE_LIMIT_PER_MINUTE", "30"))

    @property
    def db_url(self) -> str:
        """SQLite database file inside ``data_dir`` (created on first start)."""
        return f"sqlite:///{(self.data_dir / 'cropdoc.db').as_posix()}"

    def ensure_dirs(self) -> None:
        """Create writable folders on first start."""
        for path in (self.data_dir, self.data_dir / "scans", self.inbox_dir):
            path.mkdir(parents=True, exist_ok=True)
