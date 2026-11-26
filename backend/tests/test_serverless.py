"""Serverless hosting (Vercel): writable /tmp, no lifespan, proxy IPs, and dependencies in pyproject.toml."""

from __future__ import annotations

import os
import subprocess
import sys
import tomllib
from pathlib import Path

from fastapi.testclient import TestClient
from starlette.requests import Request

from app.config import Settings
from app.main import create_app
from app.ratelimit import client_key
from tests.conftest import image_bytes

ROOT = Path(__file__).resolve().parents[2]


def test_app_works_even_if_the_host_skips_lifespan(tmp_path, tiny_model_dir, diseases_file):
    """Without `with TestClient(...)` the start-up (lifespan) never runs: the first request loads everything."""
    settings = Settings(
        model_dir=tiny_model_dir,
        data_dir=tmp_path / "app",
        inbox_dir=tmp_path / "inbox",
        frontend_dist=tmp_path / "no-dist",
        diseases_file=diseases_file,
        rate_limit_per_minute=1000,
    )
    client = TestClient(create_app(settings))  # no context manager → no lifespan
    assert client.get("/api/health").json()["model_loaded"] is True
    response = client.post("/api/predict", files={"image": ("leaf.jpg", image_bytes(), "image/jpeg")})
    assert response.status_code == 200, response.text
    assert client.get("/api/scans").json()["total"] == 1


def test_on_vercel_data_goes_to_tmp_and_storage_is_marked_temporary():
    env = {**os.environ, "VERCEL": "1"}
    env.pop("CROPDOC_DATA_DIR", None)
    env.pop("CROPDOC_INBOX_DIR", None)
    code = (
        "from app.config import Settings; s = Settings(); "
        "print(s.data_dir.as_posix(), s.inbox_dir.as_posix(), s.temporary_storage, s.trust_proxy_headers)"
    )
    out = subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT / "backend",
        env=env,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    assert out == ["/tmp/cropdoc/app", "/tmp/cropdoc/inbox", "True", "True"]


def test_health_reports_temporary_storage(make_client):
    assert make_client().get("/api/health").json()["temporary_storage"] is False
    assert make_client(temporary_storage=True).get("/api/health").json()["temporary_storage"] is True


def _request(headers: dict[str, str], client_ip: str = "10.0.0.1") -> Request:
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/predict",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
        "client": (client_ip, 1234),
    }
    return Request(scope)


def test_rate_limit_key_uses_visitor_ip_only_behind_a_trusted_proxy():
    request = _request({"X-Forwarded-For": "203.0.113.7, 10.0.0.1"})
    assert client_key(request, trust_proxy_headers=False) == "10.0.0.1"  # headers can be faked: ignore
    assert client_key(request, trust_proxy_headers=True) == "203.0.113.7"
    assert client_key(_request({"X-Real-IP": "198.51.100.4"}), trust_proxy_headers=True) == "198.51.100.4"
    assert client_key(_request({}), trust_proxy_headers=True) == "10.0.0.1"


def test_root_entrypoint_exposes_the_app():
    out = subprocess.run(
        [sys.executable, "-c", "import index; print(type(index.app).__name__)"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert out == "FastAPI"


def test_pyproject_dependencies_match_backend_pins():
    """Cloud hosts install pyproject.toml; start.bat/start.sh install backend/requirements.txt. Same versions."""
    pins = {}
    for line in (ROOT / "backend" / "requirements.txt").read_text().splitlines():
        if "==" in line and not line.startswith((" ", "#")):
            requirement, _, marker = line.partition(";")
            pins.setdefault(requirement.strip(), marker.strip())
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    declared = project["dependencies"] + project["optional-dependencies"]["phone"]
    for item in declared:
        requirement = item.split(";")[0].strip()
        assert requirement in pins, f"{requirement} is not pinned in backend/requirements.txt"
    top_level = {
        "fastapi",
        "uvicorn",
        "python-multipart",
        "pydantic",
        "sqlalchemy",
        "pillow",
        "numpy",
        "onnxruntime",
    }
    assert top_level <= {item.split("==")[0] for item in declared}
    assert not any(name.startswith(("torch", "timm")) for name in (i.split("==")[0] for i in declared))


def test_read_only_data_folder_falls_back_to_temp(tmp_path):
    from app.config import with_writable_storage

    blocker = tmp_path / "not-a-folder"
    blocker.write_text("a file where the data folder should be")  # mkdir below it fails like a read-only disk
    settings = Settings(data_dir=blocker / "app", inbox_dir=blocker / "inbox", temporary_storage=False)
    usable = with_writable_storage(settings)
    assert usable.data_dir != settings.data_dir and usable.temporary_storage is True
    assert usable.data_dir.is_dir()


def test_vercel_handler_variables_alone_mean_serverless():
    env = {k: v for k, v in os.environ.items() if not k.startswith(("VERCEL", "AWS_LAMBDA", "LAMBDA_"))}
    env.pop("CROPDOC_DATA_DIR", None)
    env["__VC_HANDLER_ENTRYPOINT"] = "index.py"  # always set by Vercel's Python handler
    code = (
        "from app.config import Settings; s = Settings(); print(s.data_dir.as_posix(), s.temporary_storage)"
    )
    out = subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT / "backend",
        env=env,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    assert out == ["/tmp/cropdoc/app", "True"]


def test_failed_startup_is_reported_not_crashed(monkeypatch, tmp_path, tiny_model_dir, diseases_file):
    def broken_db(url):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr("app.main.init_db", broken_db)
    settings = Settings(
        model_dir=tiny_model_dir,
        data_dir=tmp_path / "app",
        inbox_dir=tmp_path / "inbox",
        frontend_dist=tmp_path / "no-dist",
        diseases_file=diseases_file,
    )
    with TestClient(create_app(settings)) as client:  # lifespan runs and fails, but the server stays up
        health = client.get("/api/health")
        assert health.status_code == 200
        body = health.json()
        assert body["model_loaded"] is False and "database unavailable" in body["reason"]
        assert client.get("/api/scans").status_code == 503
        predict = client.post("/api/predict", files={"image": ("leaf.jpg", image_bytes(), "image/jpeg")})
        assert predict.status_code == 503 and "could not start" in predict.json()["detail"]


def test_entrypoint_shows_the_error_when_the_app_cannot_import():
    code = """
import asyncio, sys
sys.modules["app.main"] = None  # simulate a broken install: importing app.main raises ImportError
import index
sent = []
async def receive():
    return {"type": "http.request", "body": b""}
async def send(message):
    sent.append(message)
asyncio.run(index.app({"type": "http", "method": "GET", "path": "/"}, receive, send))
print(sent[0]["status"])
print(sent[1]["body"].decode())
"""
    result = subprocess.run(
        [sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, check=True
    )
    assert result.stdout.startswith("500")
    assert "CropDoc GB could not start" in result.stdout and "ModuleNotFoundError" in result.stdout


def test_supported_python_versions_match_the_pins():
    """Cloud builders (Vercel runs `uv lock`) resolve every Python version the project claims to support.

    numpy 2.4 needs Python >= 3.11, so claiming 3.10 made the Vercel build fail ("No solution found").
    The start scripts must ask for the same minimum.
    """
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    assert project["requires-python"] == ">=3.11"
    for script in ("start.sh", "start.bat", "scripts/ensure_deps.py"):
        text = (ROOT / script).read_text()
        assert "(3, 10)" not in text and "(3, 11)" in text, script


def test_vercel_config_pins_the_settings_that_dashboards_can_override():
    """Old dashboard settings (Framework "Other", an npm Install Command, a Vite output folder) broke builds."""
    import json

    config = json.loads((ROOT / "vercel.json").read_text())
    assert config["framework"] == "fastapi"  # runs our build command inside Vercel's Python builder
    assert config["installCommand"] == ""  # empty = no custom install: Vercel installs pyproject.toml with uv
    assert (
        config["outputDirectory"] == "public" and (ROOT / "public").is_dir()
    )  # FastAPI preset's static folder
    assert "npm ci" in config["buildCommand"] and "npm run build" in config["buildCommand"]
