"""Start CropDoc GB with one command: API + web app in one process, then open the browser.

python backend/run.py              # opens http://127.0.0.1:8000
python backend/run.py --no-browser --port 8080
python backend/run.py --phone      # HTTPS on your Wi-Fi so a phone can use the live camera
"""

from __future__ import annotations

import argparse
import os
import socket
import ssl
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
    context = ssl._create_unverified_context()  # our own self-signed certificate in phone mode
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{url}/api/health", timeout=2, context=context):
                webbrowser.open(url)
                return
        except OSError:
            time.sleep(0.5)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the CropDoc GB app.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument(
        "--phone",
        action="store_true",
        help="serve over HTTPS on the local network so phones on the same Wi-Fi can use the live camera",
    )
    args = parser.parse_args()

    if args.phone:
        return run_phone_mode(args)

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


def run_phone_mode(args: argparse.Namespace) -> int:
    """HTTPS on 0.0.0.0 with a self-signed certificate, and print the address to open on the phone."""
    from app.config import Settings
    from app.phone import ensure_certificate, lan_addresses

    port = 8443 if args.port == 8000 else args.port
    while not port_is_free("127.0.0.1", port) and port < 8453:
        port += 1
    addresses = lan_addresses()
    cert, key = ensure_certificate(Settings().data_dir / "certs", addresses)
    phone_urls = [f"https://{address}:{port}" for address in addresses]
    os.environ["CROPDOC_PHONE_MODE"] = "1"
    os.environ["CROPDOC_PUBLIC_URLS"] = ",".join(phone_urls)

    line = "=" * 64
    print(f"\n  {line}\n  CropDoc GB - PHONE MODE (press Ctrl+C to stop)\n  {line}")
    print(f"  On this computer : https://localhost:{port}")
    if phone_urls:
        for phone_url in phone_urls:
            print(f"  On your phone    : {phone_url}")
        print("\n  1. Connect the phone to the SAME Wi-Fi as this computer.")
        print("  2. Open the address above in Chrome/Safari (or scan the QR code on the Live Scan page).")
        print('  3. The first time, the phone warns "connection not private": tap Advanced -> Proceed.')
        print("     (The certificate is made by this computer; data stays on your Wi-Fi.)")
        print("  4. If Windows asks about the firewall, allow access on Private networks.")
    else:
        print("  No Wi-Fi/LAN address found. Connect this computer to a network and start again.")
    print(f"  {line}\n", flush=True)
    if not args.no_browser:
        threading.Thread(target=open_when_ready, args=(f"https://localhost:{port}",), daemon=True).start()

    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        log_level="info",
        ssl_certfile=str(cert),
        ssl_keyfile=str(key),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
