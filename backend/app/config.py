"""Runtime settings, read from environment variables with safe defaults.

Every path defaults to a location inside the project folder, so unzipping the project and
running ``start.bat`` / ``start.sh`` works without any configuration.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Serverless hosts (Vercel) give a read-only project folder; only /tmp is writable, and it is
# temporary: saved scans can disappear when the host starts a fresh copy of the app.
ON_VERCEL = bool(os.environ.get("VERCEL"))
WRITABLE_ROOT = Path("/tmp/cropdoc") if ON_VERCEL else PROJECT_ROOT / "data"


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
    data_dir: Path = field(default_factory=lambda: _env_path("CROPDOC_DATA_DIR", WRITABLE_ROOT / "app"))
    inbox_dir: Path = field(default_factory=lambda: _env_path("CROPDOC_INBOX_DIR", WRITABLE_ROOT / "inbox"))
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
    # live camera mode sends ~1-2 small frames per second, so it gets its own, larger bucket
    live_rate_limit_per_minute: int = int(os.environ.get("CROPDOC_LIVE_RATE_LIMIT_PER_MINUTE", "240"))
    # set by `run.py --phone`: the app is served over HTTPS on the local network for phones
    phone_mode: bool = field(default_factory=lambda: os.environ.get("CROPDOC_PHONE_MODE", "") == "1")
    public_urls: list[str] = field(default_factory=lambda: _env_list("CROPDOC_PUBLIC_URLS", []))
    # behind a hosting proxy every request comes from the proxy's address; the real visitor's IP is
    # in X-Real-IP / X-Forwarded-For. Only trust those headers where a known proxy sets them.
    trust_proxy_headers: bool = field(
        default_factory=lambda: os.environ.get("CROPDOC_TRUST_PROXY", "1" if ON_VERCEL else "") == "1"
    )
    # True where saved scans do not survive restarts (serverless): the UI tells the user so
    temporary_storage: bool = field(
        default_factory=lambda: os.environ.get("CROPDOC_TEMPORARY_STORAGE", "1" if ON_VERCEL else "") == "1"
    )

    @property
    def db_url(self) -> str:
        """SQLite database file inside ``data_dir`` (created on first start)."""
        return f"sqlite:///{(self.data_dir / 'cropdoc.db').as_posix()}"

    def ensure_dirs(self) -> None:
        """Create writable folders on first start."""
        for path in (self.data_dir, self.data_dir / "scans", self.inbox_dir):
            path.mkdir(parents=True, exist_ok=True)
