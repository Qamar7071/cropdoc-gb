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
