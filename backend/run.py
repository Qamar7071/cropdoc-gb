"""Start CropDoc GB with one command: API + web app in one process, then open the browser.

python backend/run.py              # opens http://127.0.0.1:8000
python backend/run.py --no-browser --port 8080
"""

from __future__ import annotations

import argparse
import socket
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # make the `app` package importable


def port_is_free(host: str, port: int) -> bool:
    """True if nothing is listening on host:port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        return sock.connect_ex((host, port)) != 0


def open_when_ready(url: str, timeout: float = 90.0) -> None:
    """Poll /api/health until the server answers, then open the browser."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{url}/api/health", timeout=2):
                webbrowser.open(url)
                return
        except OSError:
            time.sleep(0.5)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the CropDoc GB app.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    port = args.port
    while not port_is_free(args.host, port) and port < args.port + 10:
        port += 1
    url = f"http://{args.host}:{port}"
    print(f"\n  CropDoc GB is starting at {url}  (press Ctrl+C to stop)\n", flush=True)
    if not args.no_browser:
        threading.Thread(target=open_when_ready, args=(url,), daemon=True).start()

    import uvicorn

    uvicorn.run("app.main:app", host=args.host, port=port, log_level="info")
    return 0


if __name__ == "__main__":
    sys.exit(main())
