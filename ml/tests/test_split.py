"""Split tests: no duplicate group ever crosses splits; the committed split matches its hash."""

from __future__ import annotations

import gzip
import io
import json

import numpy as np
import pandas as pd
import pytest

from cropdoc import paths
from cropdoc.data.split import group_aware_split, groups_crossing_splits, naive_split, split_sha256


def synthetic(n_classes: int = 5, groups_per_class: int = 40, seed: int = 0) -> tuple[np.ndarray, np.ndarray]:
    """Labels and groups where every group has 1-6 photos of one class (like leaves in PlantVillage)."""
    rng = np.random.default_rng(seed)
    labels, groups = [], []
    gid = 0
    for c in range(n_classes):
        for _ in range(groups_per_class):
            size = rng.integers(1, 7)
            labels += [c] * size
            groups += [gid] * size
            gid += 1
    return np.array(labels), np.array(groups)


def test_group_aware_split_never_separates_a_group():
    labels, groups = synthetic()
    splits = group_aware_split(labels, groups, seed=1)
    assert groups_crossing_splits(groups, splits) == 0
    assert set(splits) == {"train", "val", "test"}


def test_group_aware_split_is_stratified_and_sized():
    labels, groups = synthetic(groups_per_class=120)
    splits = group_aware_split(labels, groups, seed=1)
    fractions = pd.Series(splits).value_counts(normalize=True)
    assert abs(fractions["train"] - 0.70) < 0.05 and abs(fractions["test"] - 0.15) < 0.04
    per_class_test = pd.crosstab(labels, splits, normalize="index")["test"]
    assert per_class_test.between(0.08, 0.22).all()


def test_split_is_deterministic_for_a_seed():
    labels, groups = synthetic()
    assert (group_aware_split(labels, groups, seed=3) == group_aware_split(labels, groups, seed=3)).all()


def test_naive_split_does_leak_groups():
    """The naive split ignores groups; this is exactly the leakage we measure."""
    labels, groups = synthetic()
    assert groups_crossing_splits(groups, naive_split(labels, seed=1)) > 0


def _load(name: str) -> pd.DataFrame:
    with gzip.open(paths.SPLITS / f"{name}.csv.gz", "rb") as fh:
        return pd.read_csv(io.BytesIO(fh.read()))


@pytest.mark.data
@pytest.mark.skipif(not (paths.SPLITS / "group_aware.csv.gz").exists(), reason="split not built yet")
def test_committed_split_has_no_group_leakage_and_matches_hash():
    frame = _load("group_aware")
    assert groups_crossing_splits(frame.group.to_numpy(), frame.split.to_numpy()) == 0
    manifest = json.loads((paths.SPLITS / "manifest.json").read_text())
    assert split_sha256(frame) == manifest["splits"]["group_aware"]["sha256_csv"]
    assert frame.class_id.nunique() == 38
    # every class must appear in every split
    assert (pd.crosstab(frame.class_id, frame.split) > 0).all().all()


@pytest.mark.data
@pytest.mark.skipif(not (paths.SPLITS / "naive.csv.gz").exists(), reason="split not built yet")
def test_naive_split_matches_hash_and_same_images():
    naive, group = _load("naive"), _load("group_aware")
    manifest = json.loads((paths.SPLITS / "manifest.json").read_text())
    assert split_sha256(naive) == manifest["splits"]["naive"]["sha256_csv"]
    assert sorted(naive.path) == sorted(group.path)
