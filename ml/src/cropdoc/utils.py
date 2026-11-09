"""Small shared helpers: seeding, logging, hashing and JSON I/O.

Why seeding matters: neural-network training uses randomness (initial weights, data order,
augmentation). Fixing the seed makes a run repeatable, and running several *different* seeds
tells us how much results vary by chance — which is why we always report mean ± std.
"""

from __future__ import annotations

import csv
import hashlib
import json
import logging
import os
import random
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import numpy as np


def seed_everything(seed: int, deterministic: bool = True) -> None:
    """Seed python, numpy and torch (if installed); optionally force deterministic kernels.

    ``deterministic=True`` sets cuDNN to deterministic mode and asks torch to warn when an op has
    no deterministic implementation. GPU runs are then repeatable in distribution (we still report
    mean ± std across seeds); CPU runs are bit-exact.
    """
    random.seed(seed)
    np.random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)
    try:
        import torch
    except ImportError:  # the web app runtime does not ship torch
        return
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    if deterministic:
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False
        os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
        torch.use_deterministic_algorithms(True, warn_only=True)


def worker_init_fn(worker_id: int) -> None:
    """Give every DataLoader worker its own reproducible numpy/python seed."""
    import torch

    worker_seed = torch.initial_seed() % 2**32
    np.random.seed(worker_seed + worker_id)
    random.seed(worker_seed + worker_id)


def get_logger(name: str = "cropdoc", level: int = logging.INFO) -> logging.Logger:
    """Return a console logger with a compact, timestamped format."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s", "%H:%M:%S"))
        logger.addHandler(handler)
    logger.setLevel(level)
    return logger


class CSVLogger:
    """Append rows (dicts) to a CSV file; the header is written once from the first row's keys.

    Optionally mirrors every row to Weights & Biases when ``wandb_project`` is given and the
    ``wandb`` package is installed (it is *not* a required dependency).
    """

    def __init__(self, path: str | Path, wandb_project: str | None = None, run_name: str | None = None):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fieldnames: list[str] | None = None
        if self.path.exists() and self.path.stat().st_size > 0:
            with self.path.open(newline="") as f:
                self._fieldnames = next(csv.reader(f), None)
        self._wandb = None
        if wandb_project:
            try:
                import wandb  # type: ignore[import-not-found]

                self._wandb = wandb.init(project=wandb_project, name=run_name, reinit=True)
            except ImportError:
                get_logger().warning("wandb requested but not installed; logging to CSV only")

    def log(self, row: dict[str, Any]) -> None:
        """Write one row (missing keys are left blank, unknown keys are ignored)."""
        if self._fieldnames is None:
            self._fieldnames = list(row.keys())
            with self.path.open("w", newline="") as f:
                csv.DictWriter(f, fieldnames=self._fieldnames).writeheader()
        with self.path.open("a", newline="") as f:
            csv.DictWriter(f, fieldnames=self._fieldnames, extrasaction="ignore").writerow(row)
        if self._wandb is not None:
            self._wandb.log(row)


def sha256_file(path: str | Path, chunk_size: int = 1 << 20) -> str:
    """SHA256 hex digest of a file (used to pin splits, weights and model files)."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    """SHA256 hex digest of bytes."""
    return hashlib.sha256(data).hexdigest()


def write_json(path: str | Path, obj: Any) -> Path:
    """Write pretty JSON (creating parent folders); numpy scalars/arrays are converted."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=_json_default) + "\n")
    return path


def read_json(path: str | Path) -> Any:
    """Read JSON from a file."""
    return json.loads(Path(path).read_text())


def _json_default(obj: Any) -> Any:
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, Path):
        return str(obj)
    raise TypeError(f"not JSON serializable: {type(obj).__name__}")


@contextmanager
def timer(label: str, logger: logging.Logger | None = None) -> Iterator[dict[str, float]]:
    """Context manager that measures wall time: ``with timer("epoch") as t: ...; t["seconds"]``."""
    record: dict[str, float] = {}
    start = time.perf_counter()
    try:
        yield record
    finally:
        record["seconds"] = time.perf_counter() - start
        (logger or get_logger()).info("%s took %.1fs", label, record["seconds"])
