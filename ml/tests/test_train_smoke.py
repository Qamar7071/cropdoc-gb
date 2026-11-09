"""Training pipeline smoke tests on synthetic data (CPU, seconds): train, resume, sweep ids, bg-rand."""

from __future__ import annotations

import json

import numpy as np
from PIL import Image

from cropdoc.config import load_config, parse_override, run_id
from cropdoc.data.background import BackgroundRandomizer, procedural_background
from cropdoc.data.synthetic import make_synthetic_dataset
from cropdoc.train import train_run


def smoke_config(tmp_path, **overrides) -> dict:
    items = [f"data.synthetic_root={tmp_path / 'synthetic'}", *[f"{k}={v}" for k, v in overrides.items()]]
    return load_config("smoke.yaml", overrides=items)


def test_config_merge_and_override():
    config = load_config("experiments/r18_std_naive.yaml", overrides=["train.epochs=3", "seed=2"])
    assert config["model"]["arch"] == "resnet18" and config["data"]["split"] == "naive"
    assert config["train"]["epochs"] == 3 and config["seed"] == 2 and config["train"]["lr_head"] == 1e-3
    assert parse_override("a.b=[1, 2]") == {"a": {"b": [1, 2]}}


def test_run_id_ignores_name_but_not_settings():
    a = load_config("experiments/imb_none.yaml")
    b = load_config("experiments/r18_std.yaml")
    assert run_id(a) == run_id(b), "identical settings must share one run"
    assert run_id(a) != run_id(load_config("experiments/r18_std.yaml", overrides=["seed=1"]))


def test_smoke_training_writes_metrics_and_logits(tmp_path):
    run_dir = tmp_path / "run"
    metrics = train_run(smoke_config(tmp_path), run_dir)
    assert (run_dir / "metrics.json").exists() and (run_dir / "best.pt").exists()
    assert {"val", "test"} <= set(metrics["sets"])
    assert 0.0 <= metrics["sets"]["test"]["accuracy"] <= 1.0
    logits = np.load(run_dir / "logits_test.npz")
    assert logits["logits"].shape[0] == logits["labels"].shape[0]


def test_resume_continues_from_checkpoint(tmp_path):
    run_dir = tmp_path / "resume"
    train_run(smoke_config(tmp_path, **{"train.epochs": 1}), run_dir)
    (run_dir / "metrics.json").unlink()  # pretend the session died after epoch 1
    metrics = train_run(smoke_config(tmp_path, **{"train.epochs": 2}), run_dir)
    epochs = [row["epoch"] for row in metrics["history"]]
    assert epochs == [1, 2], "epoch 1 must not be retrained after resume"
    assert json.loads((run_dir / "metrics.json").read_text())["best_epoch"] in (1, 2)


def test_class_balance_options_run(tmp_path):
    for option in ("weighted_loss", "balanced_sampler"):
        metrics = train_run(
            smoke_config(tmp_path, **{"data.class_balance": option, "train.epochs": 1}), tmp_path / option
        )
        assert "test" in metrics["sets"]


def test_background_randomizer_keeps_the_leaf(tmp_path):
    frame = make_synthetic_dataset(tmp_path / "s", n_classes=1, per_class=2)
    row = frame.iloc[0]
    with Image.open(row.path) as image:
        original = image.convert("RGB")
    randomized = BackgroundRandomizer([row.seg_path], None, p=1.0, seed=0)(original, 0)
    assert randomized.size == original.size
    assert np.asarray(randomized).std() > 0
    background = procedural_background((32, 32), __import__("random").Random(0))
    assert background.size == (32, 32)
