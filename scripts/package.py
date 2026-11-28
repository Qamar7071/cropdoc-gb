"""Build dist/cropdoc-gb-complete.zip (``make package``).

Steps: build the frontend → run the tests → refresh docs numbers from results/ → zip.
The zip contains: backend, built frontend (+ source), ml code, models/active, results (without the
UI screenshots), scripts, docs, README, MODEL_CARD, start.bat, start-phone.bat, start.sh, docker-compose.yml.
Excluded: data (except READMEs), node_modules, virtual environments, caches, .git.

    python scripts/package.py                 # full build
    python scripts/package.py --skip-tests    # faster, when tests were just run
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
ZIP_PATH = DIST / "cropdoc-gb-complete.zip"
TOP = "cropdoc-gb"
MAX_MODEL_MB = 100

INCLUDE = [
    "backend",
    "frontend",
    "ml",
    "models/active",
    "results",
    "scripts",
    "docs",
    "public",  # Vercel outputDirectory (vercel.json); robots.txt keeps the folder present
    "README.md",
    "MODEL_CARD.md",
    "CLAUDE.md",
    "LICENSE",
    "Makefile",
    "pyproject.toml",
    "requirements-dev.in",
    "requirements-dev.txt",
    "start.bat",
    "start-phone.bat",
    "start.sh",
    "Dockerfile",
    "index.py",
    "vercel.json",
    ".vercelignore",
    "docker-compose.yml",
    ".dockerignore",
    ".gitattributes",
    ".gitignore",
    ".pre-commit-config.yaml",
    ".github/workflows/ci.yml",
    "data/README.md",
    "data/field_test/README.md",
]
SKIP_DIR_NAMES = {
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    "test-results",
    "playwright-report",
    ".venv",
}
SKIP_PREFIXES = ("results/ui", "ml/cache", "ml/runs")
SKIP_SUFFIXES = (".pyc", ".pt", ".pth", ".npz", ".tsbuildinfo")
EXECUTABLE = {"start.sh"}


def run(cmd: list[str], cwd: Path = ROOT, env: dict | None = None) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(
        cmd,
        cwd=cwd,
        check=True,
        env={**os.environ, **(env or {})},
        shell=(os.name == "nt" and cmd[0] == "npm"),
    )


def build_frontend() -> None:
    frontend = ROOT / "frontend"
    if not (frontend / "node_modules").exists():
        run(["npm", "ci"], cwd=frontend)
    run(["npm", "run", "build"], cwd=frontend)


def run_tests() -> None:
    env = {"PYTHONPATH": os.pathsep.join([str(ROOT / "ml" / "src"), str(ROOT / "backend")])}
    run([sys.executable, "-m", "pytest", "-q", "-p", "no:warnings"], env=env)
    run(["npm", "run", "test"], cwd=ROOT / "frontend")


def refresh_docs() -> None:
    env = {"PYTHONPATH": str(ROOT / "ml" / "src")}
    run([sys.executable, "-m", "cropdoc.report"], env=env)


def iter_files() -> list[Path]:
    files: list[Path] = []
    for entry in INCLUDE:
        path = ROOT / entry
        if path.is_file():
            files.append(path)
            continue
        for child in sorted(path.rglob("*")):
            rel = child.relative_to(ROOT).as_posix()
            if not child.is_file() or any(part in SKIP_DIR_NAMES for part in child.relative_to(ROOT).parts):
                continue
            if rel.startswith(SKIP_PREFIXES) or rel.endswith(SKIP_SUFFIXES):
                continue
            files.append(child)
    return files


def git_commit() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def build_zip() -> Path:
    model = ROOT / "models" / "active" / "model.onnx"
    if not (ROOT / "frontend" / "dist" / "index.html").exists():
        raise SystemExit("frontend/dist is missing: run without --skip-build")
    if model.exists() and model.stat().st_size > MAX_MODEL_MB * 1e6:
        raise SystemExit(
            f"model.onnx is larger than {MAX_MODEL_MB} MB: publish it separately and document the download"
        )
    card = json.loads((ROOT / "models" / "active" / "model_card.json").read_text()) if model.exists() else {}
    files = iter_files()
    DIST.mkdir(exist_ok=True)
    tmp = ZIP_PATH.with_suffix(".tmp")
    manifest = {
        "name": "CropDoc GB",
        "built_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "git_commit": git_commit(),
        "model_version": card.get("model_version"),
        "model_sha256": hashlib.sha256(model.read_bytes()).hexdigest() if model.exists() else None,
        "files": len(files) + 1,
    }
    with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            rel = path.relative_to(ROOT).as_posix()
            info = zipfile.ZipInfo(f"{TOP}/{rel}", date_time=time.localtime(path.stat().st_mtime)[:6])
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o755 if rel in EXECUTABLE else 0o644) << 16
            archive.writestr(info, path.read_bytes())
        archive.writestr(f"{TOP}/MANIFEST.json", json.dumps(manifest, indent=2))
    shutil.move(tmp, ZIP_PATH)
    return ZIP_PATH


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--skip-build", action="store_true")
    parser.add_argument("--skip-tests", action="store_true")
    args = parser.parse_args()
    if not args.skip_build:
        build_frontend()
    if not args.skip_tests:
        run_tests()
    refresh_docs()
    path = build_zip()
    size_mb = path.stat().st_size / 1e6
    print(f"\nCreated {path} ({size_mb:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
