"""Seeding and helper tests."""

from __future__ import annotations

import numpy as np
import torch

from cropdoc.utils import CSVLogger, read_json, seed_everything, sha256_bytes, sha256_file, write_json


def test_seed_everything_makes_numpy_and_torch_repeatable():
    seed_everything(123)
    a = (np.random.rand(3), torch.rand(3))
    seed_everything(123)
    b = (np.random.rand(3), torch.rand(3))
    assert np.allclose(a[0], b[0]) and torch.equal(a[1], b[1])
    assert torch.backends.cudnn.deterministic is True


def test_csv_logger_appends_rows(tmp_path):
    log = CSVLogger(tmp_path / "log.csv")
    log.log({"epoch": 1, "loss": 0.5})
    log.log({"epoch": 2, "loss": 0.25, "extra": "ignored"})
    lines = (tmp_path / "log.csv").read_text().strip().splitlines()
    assert lines == ["epoch,loss", "1,0.5", "2,0.25"]


def test_hash_and_json_roundtrip(tmp_path):
    path = write_json(tmp_path / "x.json", {"a": np.float32(0.5), "b": np.arange(2)})
    assert read_json(path) == {"a": 0.5, "b": [0, 1]}
    assert sha256_file(path) == sha256_bytes(path.read_bytes())
