"""Install the app's runtime dependencies into the current Python, only when they changed.

Called by start.bat / start.sh with the project's virtual-environment Python. The first run needs
internet (about 50 MB of wheels: FastAPI, ONNX Runtime, NumPy, Pillow, SQLAlchemy). Later runs skip
the install unless backend/requirements.txt changed.
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIREMENTS = ROOT / "backend" / "requirements.txt"
MARKER = Path(sys.prefix) / "cropdoc-deps.sha256"


def main() -> int:
    if sys.version_info < (3, 10):  # noqa: UP036 - runs on the user's own Python, which may be old
        print("Python 3.10 or newer is required (3.11 recommended).")
        return 1
    digest = hashlib.sha256(REQUIREMENTS.read_bytes()).hexdigest()
    if MARKER.exists() and MARKER.read_text().strip() == digest:
        return 0
    print("Installing CropDoc GB dependencies (first run only; needs internet, about 50 MB)...", flush=True)
    command = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--disable-pip-version-check",
        "-q",
        "-r",
        str(REQUIREMENTS),
    ]
    result = subprocess.run(command)
    if result.returncode != 0:
        print(
            "\nInstalling dependencies failed. Check your internet connection and try again.\n"
            "If you use Python 3.13 or newer and an error mentions a missing wheel, install Python 3.11 "
            "from https://www.python.org/downloads/ and run the start script again."
        )
        return result.returncode
    MARKER.write_text(digest)
    return 0


if __name__ == "__main__":
    sys.exit(main())
