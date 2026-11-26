"""Install the app's runtime dependencies (only when they changed) and check the AI engine can start.

Called by start.bat / start.sh with the project's virtual-environment Python. The first run needs
internet (about 50 MB of wheels: FastAPI, ONNX Runtime, NumPy, Pillow, SQLAlchemy). Later runs skip
the install unless backend/requirements.txt changed.

Every start also checks that ONNX Runtime really loads. On Windows the usual reason it does not is a
missing or outdated Microsoft Visual C++ Redistributable; we explain that and, only if you agree,
install it with winget (Windows' built-in package manager), or open the official download link.
The app starts either way and shows the same guidance in the browser.
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIREMENTS = ROOT / "backend" / "requirements.txt"
MARKER = Path(sys.prefix) / "cropdoc-deps.sha256"
VC_REDIST_URL = "https://aka.ms/vs/17/release/vc_redist.x64.exe"
WINGET_ID = "Microsoft.VCRedist.2015+.x64"


def install_requirements() -> int:
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


def engine_error() -> str | None:
    """Try importing ONNX Runtime in a fresh process; return the error text, or None if it works."""
    result = subprocess.run([sys.executable, "-c", "import onnxruntime"], capture_output=True, text=True)
    if result.returncode == 0:
        return None
    lines = [line for line in result.stderr.strip().splitlines() if line.strip()]
    return lines[-1] if lines else "unknown error"


def ask(question: str) -> bool:
    try:
        return input(f"{question} [Y/n] ").strip().lower() in ("", "y", "yes")
    except EOFError:  # not an interactive console
        return False


def fix_windows_runtime(error: str) -> None:
    print(
        "\n" + "=" * 78 + "\n"
        "  The AI engine (ONNX Runtime) could not start:\n"
        f"    {error}\n"
        "  On Windows this almost always means the Microsoft Visual C++ Redistributable (x64)\n"
        "  is missing or outdated. It is a free, official Microsoft component.\n" + "=" * 78
    )
    if shutil.which("winget") and ask("Install/update it now with winget (Windows may ask for permission)?"):
        subprocess.run(
            [
                "winget",
                "install",
                "--id",
                WINGET_ID,
                "-e",
                "--accept-package-agreements",
                "--accept-source-agreements",
            ]
        )
        if engine_error() is None:
            print("Fixed: the AI engine starts now.\n")
            return
        print("The engine still does not start. A restart of the computer may be needed after the install.")
    else:
        print(f"Download and run the installer from:\n    {VC_REDIST_URL}")
        if ask("Open the download link in your browser now?"):
            webbrowser.open(VC_REDIST_URL)
    print("Then run start.bat again. More help: README.md, section 'Troubleshooting'.\n")


def main() -> int:
    if sys.version_info < (3, 11):  # noqa: UP036 - runs on the user's own Python, which may be old
        print("Python 3.11 or newer is required.")
        return 1
    code = install_requirements()
    if code != 0:
        return code
    error = engine_error()
    if error is not None:
        if sys.platform == "win32" and "DLL load failed" in error:
            fix_windows_runtime(error)
        else:
            print(
                f"\nWarning: the AI engine could not be imported ({error}). See README.md 'Troubleshooting'.\n"
            )
    return 0  # start the app anyway: it shows the same guidance in the browser


if __name__ == "__main__":
    sys.exit(main())
