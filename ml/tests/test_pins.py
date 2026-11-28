"""The app and the training code are installed together (CI, `make setup`), so every package pinned in
both lock files must have the same version (a mismatch makes pip stop with "ResolutionImpossible")."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PIN = re.compile(r"^([A-Za-z0-9_.\-]+)==([^\s;]+)")


def pins(path: Path) -> dict[str, set[str]]:
    found: dict[str, set[str]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = PIN.match(line.strip())
        if match:
            name = re.sub(r"[-_.]+", "-", match.group(1)).lower()
            found.setdefault(name, set()).add(match.group(2))
    return found


def clashes(a: dict[str, set[str]], b: dict[str, set[str]]) -> dict[str, tuple]:
    return {name: (sorted(a[name]), sorted(b[name])) for name in a.keys() & b.keys() if a[name] != b[name]}


def test_backend_and_ml_lock_files_agree():
    backend, ml = pins(ROOT / "backend/requirements.txt"), pins(ROOT / "ml/requirements.txt")
    assert len(backend) > 10 and len(ml) > 10
    assert clashes(backend, ml) == {}


def test_colab_lock_matches_the_ml_lock():
    assert clashes(pins(ROOT / "ml/requirements.txt"), pins(ROOT / "ml/requirements-colab.txt")) == {}
