"""Runtime settings, read from environment variables with safe defaults.

Every path defaults to a location inside the project folder, so unzipping the project and
running ``start.bat`` / ``start.sh`` works without any configuration.
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass, field, replace
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Serverless hosts (Vercel, AWS Lambda) give a read-only project folder; only the temp folder is
# writable, and it is temporary: saved scans can disappear when the host starts a fresh copy.
# Several signals, because not every host exposes the same variables at runtime
# (Vercel's own handler always sets __VC_HANDLER_ENTRYPOINT; VERCEL=1 can be switched off).
SERVERLESS_SIGNALS = (
    "VERCEL",
    "VERCEL_ENV",
    "VERCEL_URL",
    "VERCEL_REGION",
    "VERCEL_IPC_PATH",
    "__VC_HANDLER_ENTRYPOINT",
    "AWS_LAMBDA_FUNCTION_NAME",
    "LAMBDA_TASK_ROOT",
)


def on_serverless() -> bool:
    """True when running as a serverless function (checked when Settings are created)."""
    return any(os.environ.get(name) for name in SERVERLESS_SIGNALS)


def temp_root() -> Path:
    return Path(tempfile.gettempdir()) / "cropdoc"


def _writable_root() -> Path:
    return temp_root() if on_serverless() else PROJECT_ROOT / "data"


def _flag(name: str, serverless_default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return serverless_default and on_serverless()
    return value == "1"


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
    data_dir: Path = field(default_factory=lambda: _env_path("CROPDOC_DATA_DIR", _writable_root() / "app"))
    inbox_dir: Path = field(
        default_factory=lambda: _env_path("CROPDOC_INBOX_DIR", _writable_root() / "inbox")
    )
    frontend_dist: Path = field(
        default_factory=lambda: _env_path("CROPDOC_FRONTEND_DIST", PROJECT_ROOT / "frontend" / "dist")
    )
    diseases_file: Path = field(
        default_factory=lambda: _env_path(
            "CROPDOC_DISEASES_FILE", Path(__file__).parent / "data" / "diseases.json"
        )
    )
    crops_file: Path = field(
        default_factory=lambda: _env_path("CROPDOC_CROPS_FILE", Path(__file__).parent / "data" / "crops.json")
    )
    tips_file: Path = field(
        default_factory=lambda: _env_path("CROPDOC_TIPS_FILE", Path(__file__).parent / "data" / "tips.json")
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
    weather_enabled: bool = field(
        default_factory=lambda: os.environ.get("CROPDOC_WEATHER", "on").lower() != "off"
    )
    assistant_model: str = field(
        default_factory=lambda: os.environ.get("CROPDOC_ASSISTANT_MODEL", "claude-opus-5-5")
    )
    assistant_effort: str = field(
        default_factory=lambda: os.environ.get("CROPDOC_ASSISTANT_EFFORT", "medium")
    )
    assistant_rate_limit_per_minute: int = int(
        os.environ.get("CROPDOC_ASSISTANT_RATE_LIMIT_PER_MINUTE", "20")
    )
    # set by `run.py --phone`: the app is served over HTTPS on the local network for phones
    phone_mode: bool = field(default_factory=lambda: os.environ.get("CROPDOC_PHONE_MODE", "") == "1")
    public_urls: list[str] = field(default_factory=lambda: _env_list("CROPDOC_PUBLIC_URLS", []))
    # behind a hosting proxy every request comes from the proxy's address; the real visitor's IP is
    # in X-Real-IP / X-Forwarded-For. Only trust those headers where a known proxy sets them.
    trust_proxy_headers: bool = field(default_factory=lambda: _flag("CROPDOC_TRUST_PROXY", True))
    # True where saved scans do not survive restarts (serverless): the UI tells the user so
    temporary_storage: bool = field(default_factory=lambda: _flag("CROPDOC_TEMPORARY_STORAGE", True))

    @property
    def db_url(self) -> str:
        """SQLite database file inside ``data_dir`` (created on first start)."""
        return f"sqlite:///{(self.data_dir / 'cropdoc.db').as_posix()}"

    def ensure_dirs(self) -> None:
        """Create writable folders on first start."""
        for path in (self.data_dir, self.data_dir / "scans", self.inbox_dir):
            path.mkdir(parents=True, exist_ok=True)


def with_writable_storage(settings: Settings) -> Settings:
    """Settings whose data folders can really be written; else the same settings using the temp folder.

    Protects against read-only project folders (serverless hosts, a copy on a CD, locked school PCs):
    instead of crashing at start-up, scans are kept in the temp folder and marked as temporary.
    """
    try:
        settings.ensure_dirs()
        probe = settings.data_dir / f".write-test-{os.getpid()}"
        probe.write_bytes(b"")
        probe.unlink()
        return settings
    except OSError:
        root = temp_root()
        fallback = replace(settings, data_dir=root / "app", inbox_dir=root / "inbox", temporary_storage=True)
        fallback.ensure_dirs()
        return fallback
