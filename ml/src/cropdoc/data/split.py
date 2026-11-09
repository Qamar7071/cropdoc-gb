"""Train/val/test splits: a group-aware split (no leaf in two splits) and a naive one (for comparison).

Both are stratified (each split keeps roughly the same class proportions) and use the same
70/15/15 sizes, so the only difference is whether photos of the same leaf can be separated.
"""

from __future__ import annotations

import io

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedGroupKFold, train_test_split

from cropdoc.utils import sha256_bytes

SPLIT_NAMES = ("train", "val", "test")


def group_aware_split(
    labels: np.ndarray, groups: np.ndarray, seed: int = 42, n_folds: int = 20, val_folds: int = 3, test_folds: int = 3
) -> np.ndarray:
    """Assign 'train'/'val'/'test' so that every group sits in exactly one split.

    StratifiedGroupKFold cuts the data into ``n_folds`` folds (5% each) that respect groups and
    balance classes; 3 folds → test (15%), 3 → val (15%), the rest → train (70%).
    """
    folds = np.empty(len(labels), dtype=int)
    splitter = StratifiedGroupKFold(n_splits=n_folds, shuffle=True, random_state=seed)
    for fold, (_, held) in enumerate(splitter.split(np.zeros(len(labels)), labels, groups)):
        folds[held] = fold
    out = np.full(len(labels), "train", dtype=object)
    out[folds < test_folds] = "test"
    out[(folds >= test_folds) & (folds < test_folds + val_folds)] = "val"
    return out


def naive_split(labels: np.ndarray, seed: int = 42, val: float = 0.15, test: float = 0.15) -> np.ndarray:
    """Stratified random split that ignores groups (what most tutorials do)."""
    index = np.arange(len(labels))
    train_val, test_idx = train_test_split(index, test_size=test, stratify=labels, random_state=seed)
    train_idx, val_idx = train_test_split(
        train_val, test_size=val / (1 - test), stratify=labels[train_val], random_state=seed
    )
    out = np.full(len(labels), "train", dtype=object)
    out[val_idx] = "val"
    out[test_idx] = "test"
    return out


def groups_crossing_splits(groups: np.ndarray, splits: np.ndarray) -> int:
    """Number of groups whose members are spread over more than one split (0 = no leakage)."""
    frame = pd.DataFrame({"g": groups, "s": splits})
    return int((frame.groupby("g")["s"].nunique() > 1).sum())


def split_csv_bytes(frame: pd.DataFrame) -> bytes:
    """Deterministic CSV encoding (used for the SHA256 that pins a split)."""
    buffer = io.StringIO()
    frame.to_csv(buffer, index=False, lineterminator="\n")
    return buffer.getvalue().encode("utf-8")


def split_sha256(frame: pd.DataFrame) -> str:
    """SHA256 of the deterministic CSV encoding."""
    return sha256_bytes(split_csv_bytes(frame))


def summarize(frame: pd.DataFrame, split_col: str = "split") -> dict:
    """Counts per split and per class/split (for the manifest and the audit)."""
    per_split = frame[split_col].value_counts().reindex(SPLIT_NAMES, fill_value=0)
    return {
        "n_images": int(len(frame)),
        "per_split": {k: int(v) for k, v in per_split.items()},
        "fraction": {k: round(float(v) / len(frame), 4) for k, v in per_split.items()},
    }
