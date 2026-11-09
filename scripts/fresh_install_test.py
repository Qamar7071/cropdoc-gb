"""Fresh-machine test: unzip the package into an empty folder, run start.sh, verify it really works.

Checks: /api/health reports a loaded model, one real prediction on a real test photo succeeds,
the scan is saved, the dashboard counts it, and the built frontend is served.
(Linux/macOS; start.bat is the Windows equivalent and is not exercised here.)

    python scripts/fresh_install_test.py [path/to/cropdoc-gb-complete.zip]
"""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import urllib.request
import uuid
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PORT = int(os.environ.get("FRESH_PORT", "8790"))
BASE = f"http://127.0.0.1:{PORT}"


def get_json(path: str) -> dict:
    with urllib.request.urlopen(BASE + path, timeout=30) as response:
        return json.loads(response.read())


def post_image(path: str, image: Path) -> dict:
    boundary = uuid.uuid4().hex
    body = (
        (
            f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="{image.name}"\r\n'
            "Content-Type: image/jpeg\r\n\r\n"
        ).encode()
        + image.read_bytes()
        + f"\r\n--{boundary}--\r\n".encode()
    )
    request = urllib.request.Request(
        BASE + path, data=body, headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read())


def main() -> int:
    archive = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "dist" / "cropdoc-gb-complete.zip"
    workdir = Path(tempfile.mkdtemp(prefix="cropdoc-fresh-"))
    print(f"unzipping {archive} into empty folder {workdir}")
    with zipfile.ZipFile(archive) as zf:
        zf.extractall(workdir)
    app = workdir / "cropdoc-gb"
    os.chmod(app / "start.sh", 0o755)
    log = (workdir / "server.log").open("w")
    started = time.time()
    server = subprocess.Popen(
        ["./start.sh", "--no-browser", "--port", str(PORT)],
        cwd=app,
        stdout=log,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    try:
        for _ in range(600):  # first run installs dependencies (up to ~10 min on slow links)
            try:
                health = get_json("/api/health")
                break
            except OSError:
                if server.poll() is not None:
                    raise SystemExit("server exited early; see " + str(workdir / "server.log")) from None
                time.sleep(1)
        else:
            raise SystemExit("server did not start in time")
        startup = time.time() - started
        assert health["model_loaded"], health
        example = app / "frontend" / "dist" / "examples" / "early-blight.jpg"
        result = post_image("/api/predict", example)
        stats = get_json("/api/stats")
        with urllib.request.urlopen(BASE + "/scanner", timeout=30) as response:
            page = response.read().decode()
        report = {
            "unzipped_to": str(workdir),
            "first_start_seconds_including_install": round(startup, 1),
            "health": {k: health[k] for k in ("model_loaded", "model_version", "num_classes")},
            "prediction": {k: result[k] for k in ("class_id", "status", "saved")}
            | {"confidence": round(result["confidence"], 4)},
            "dashboard_total_scans": stats["total_scans"],
            "frontend_served": '<div id="root">' in page,
        }
        print(json.dumps(report, indent=2))
        ok = report["frontend_served"] and result["saved"] and stats["total_scans"] == 1
        print("FRESH INSTALL TEST:", "PASSED" if ok else "FAILED")
        return 0 if ok else 1
    finally:
        os.killpg(server.pid, signal.SIGTERM)
        server.wait(timeout=30)
        log.close()
        if os.environ.get("KEEP_FRESH_DIR") != "1":
            shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
