"""Config-driven training (GPU on Colab, CPU for smoke tests) with checkpoint/resume.

    python -m cropdoc.train --config experiments/r18_std.yaml seed=1
    python -m cropdoc.train --config smoke.yaml            # synthetic data, seconds on CPU

Recipe (intuition):
* pretrained models first train only the new head for ``frozen_epochs`` (the backbone's ImageNet
  features stay intact), then everything trains with a 10× smaller learning rate for the backbone;
* AdamW + warmup + cosine learning-rate decay; mixed precision (fp16) on GPU;
* early stopping on validation macro-F1; the best epoch is kept;
* class imbalance: none, class-weighted loss, or a balanced sampler (compared in block A);
* every epoch writes ``last.pt`` (model + optimizer + scheduler + RNG), so a Colab disconnect resumes
  where it stopped; ``metrics.json`` marks a finished run.
After training, logits on every evaluation set are saved, so all analyses run later on CPU.
"""

from __future__ import annotations

import argparse
import math
import random
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import accuracy_score, f1_score
from torch import nn
from torch.utils.data import DataLoader, WeightedRandomSampler

from cropdoc import paths
from cropdoc.calibration import expected_calibration_error, fit_temperature, softmax
from cropdoc.config import load_config, run_id
from cropdoc.data.background import BackgroundRandomizer
from cropdoc.data.classes import CLASS_IDS
from cropdoc.data.datasets import ManifestDataset
from cropdoc.data.transforms import eval_transform, train_transform
from cropdoc.models import build_model
from cropdoc.utils import CSVLogger, get_logger, seed_everything, worker_init_fn, write_json

log = get_logger("cropdoc.train")


# ----------------------------------------------------------------------------- data
def load_frames(config: dict) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, int]:
    """train / val / test frames (with seg_path) and the number of classes."""
    data = config["data"]
    if data.get("synthetic"):
        from cropdoc.data.synthetic import make_synthetic_dataset

        frame = make_synthetic_dataset(
            Path(data["synthetic_root"]), n_classes=data.get("synthetic_classes", 3)
        )
        num_classes = frame.label.nunique()
    else:
        from cropdoc.quick import load_split

        frame = load_split(data["split"])
        manifest = (
            pd.read_csv(paths.CACHE / "manifest.csv", keep_default_na=False)[["path", "seg_path"]]
            if (paths.CACHE / "manifest.csv").exists()
            else pd.DataFrame(columns=["path", "seg_path"])
        )
        frame = frame.merge(manifest, on="path", how="left").fillna({"seg_path": ""})
        num_classes = len(CLASS_IDS)
    excluded = set(data.get("exclude_classes") or [])
    train = frame[(frame.split == "train") & ~frame.class_id.isin(excluded)]
    val = frame[(frame.split == "val") & ~frame.class_id.isin(excluded)]
    test = frame[frame.split == "test"]
    if data.get("max_train_per_class"):
        train = pd.concat(
            [
                g.sample(min(len(g), data["max_train_per_class"]), random_state=config["seed"])
                for _, g in train.groupby("label")
            ]
        )
    return train.reset_index(drop=True), val.reset_index(drop=True), test.reset_index(drop=True), num_classes


def make_loaders(config: dict, train: pd.DataFrame, val: pd.DataFrame, num_classes: int):
    data, t = config["data"], config["train"]
    policy = data["aug"]
    image_fn = None
    if policy in ("bgrand", "combined"):
        bg_dir = Path(data.get("background_dir") or "")
        image_fn = BackgroundRandomizer(
            train.seg_path.tolist(),
            bg_dir if bg_dir.is_absolute() else paths.ROOT / bg_dir,
            p=data.get("bg_p", 0.8),
            seed=config["seed"],
        )
    train_set = ManifestDataset(train, train_transform(policy, crop=data["img_size"]), image_fn=image_fn)
    generator = torch.Generator().manual_seed(config["seed"])
    counts = np.bincount(train.label, minlength=num_classes).astype(np.float64)
    sampler = None
    if data["class_balance"] == "balanced_sampler":
        weights = 1.0 / counts[train.label.to_numpy()]
        sampler = WeightedRandomSampler(
            torch.as_tensor(weights), num_samples=len(train), replacement=True, generator=generator
        )
    loader_args = {
        "num_workers": data["num_workers"],
        "worker_init_fn": worker_init_fn,
        "pin_memory": torch.cuda.is_available(),
        "persistent_workers": data["num_workers"] > 0,
    }
    train_loader = DataLoader(
        train_set,
        batch_size=t["batch_size"],
        shuffle=sampler is None,
        sampler=sampler,
        generator=generator,
        drop_last=len(train) > t["batch_size"],
        **loader_args,
    )
    val_loader = DataLoader(
        ManifestDataset(val, eval_transform(crop=data["img_size"])),
        batch_size=t["batch_size"] * 2,
        **{k: v for k, v in loader_args.items() if k != "worker_init_fn"},
    )
    class_weights = None
    if data["class_balance"] == "weighted_loss":
        present = counts > 0
        w = np.zeros(num_classes)
        w[present] = counts[present].sum() / (present.sum() * counts[present])
        class_weights = torch.tensor(w, dtype=torch.float32)
    return train_loader, val_loader, class_weights


# ----------------------------------------------------------------------------- training
def lr_lambdas(config: dict, steps_per_epoch: int):
    """Per-group schedules: backbone (0 while frozen, then warmup+cosine) and head (constant, then warmup+cosine)."""
    t = config["train"]
    frozen_steps = t["frozen_epochs"] * steps_per_epoch
    total = max(1, t["epochs"] * steps_per_epoch - frozen_steps)
    warmup = max(1, int(t.get("warmup_epochs", 1) * steps_per_epoch))

    def cosine(step: int) -> float:
        s = step - frozen_steps
        if s < warmup:
            return (s + 1) / warmup
        return 0.5 * (1 + math.cos(math.pi * min(1.0, (s - warmup) / max(1, total - warmup))))

    def backbone(step: int) -> float:
        return 0.0 if step < frozen_steps else cosine(step)

    def head(step: int) -> float:
        return 1.0 if step < frozen_steps else cosine(step)

    return [backbone, head]


@torch.no_grad()
def predict_logits(
    model: nn.Module, loader: DataLoader, device: torch.device, amp: bool
) -> tuple[np.ndarray, np.ndarray]:
    model.eval()
    outputs, labels = [], []
    for images, y, _ in loader:
        with torch.autocast(
            device_type=device.type, dtype=torch.float16, enabled=amp and device.type == "cuda"
        ):
            outputs.append(model(images.to(device, non_blocking=True)).float().cpu().numpy())
        labels.append(y.numpy())
    return np.concatenate(outputs), np.concatenate(labels)


def macro_f1(labels: np.ndarray, preds: np.ndarray) -> float:
    present = sorted(set(labels.tolist()))
    return float(f1_score(labels, preds, labels=present, average="macro", zero_division=0))


def train_run(config: dict, run_dir: Path) -> dict:
    """Train (or resume) one run and evaluate it; returns the metrics dict (also written to metrics.json)."""
    run_dir.mkdir(parents=True, exist_ok=True)
    seed_everything(config["seed"], deterministic=config.get("deterministic", True))
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    t = config["train"]
    amp = bool(t.get("amp", True)) and device.type == "cuda"
    train, val, test, num_classes = load_frames(config)
    train_loader, val_loader, class_weights = make_loaders(config, train, val, num_classes)

    model = build_model(
        config["model"]["arch"],
        num_classes,
        pretrained=config["model"].get("pretrained", True),
        dropout=config["model"].get("dropout", 0.2),
    ).to(device)
    backbone_params = list(model.backbone.parameters())
    head_params = list(model.fc.parameters())
    optimizer = torch.optim.AdamW(
        [{"params": backbone_params, "lr": t["lr_backbone"]}, {"params": head_params, "lr": t["lr_head"]}],
        weight_decay=t["weight_decay"],
    )
    scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, lr_lambdas(config, len(train_loader)))
    scaler = torch.amp.GradScaler("cuda", enabled=amp)
    criterion = nn.CrossEntropyLoss(
        weight=class_weights.to(device) if class_weights is not None else None,
        label_smoothing=t.get("label_smoothing", 0.0),
    )
    state = {"epoch": 0, "best_f1": -1.0, "best_epoch": 0, "stale": 0, "history": []}

    last = run_dir / "last.pt"
    if last.exists():  # resume after a disconnect
        checkpoint = torch.load(last, map_location=device, weights_only=False)
        model.load_state_dict(checkpoint["model"])
        optimizer.load_state_dict(checkpoint["optimizer"])
        scheduler.load_state_dict(checkpoint["scheduler"])
        scaler.load_state_dict(checkpoint["scaler"])
        state = checkpoint["state"]
        torch.set_rng_state(checkpoint["rng"]["torch"])
        np.random.set_state(checkpoint["rng"]["numpy"])
        random.setstate(checkpoint["rng"]["python"])
        log.info("resumed %s at epoch %d", run_dir.name, state["epoch"])

    logger = CSVLogger(
        run_dir / "log.csv",
        wandb_project=config.get("logging", {}).get("wandb_project"),
        run_name=run_dir.name,
    )
    started = time.time()
    while state["epoch"] < t["epochs"] and state["stale"] < t["patience"]:
        epoch = state["epoch"]
        frozen = epoch < t["frozen_epochs"] and config["model"].get("pretrained", True)
        model.train()
        model.backbone.requires_grad_(not frozen)
        if frozen:
            model.backbone.eval()  # keep BatchNorm statistics of the pretrained backbone
        running, seen, epoch_start = 0.0, 0, time.time()
        for images, labels, _ in train_loader:
            images, labels = images.to(device, non_blocking=True), labels.to(device, non_blocking=True)
            with torch.autocast(device_type=device.type, dtype=torch.float16, enabled=amp):
                loss = criterion(model(images), labels)
            optimizer.zero_grad(set_to_none=True)
            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()
            scheduler.step()
            running += loss.item() * len(labels)
            seen += len(labels)
        logits, y = predict_logits(model, val_loader, device, amp)
        preds = logits.argmax(1)
        row = {
            "epoch": epoch + 1,
            "frozen": frozen,
            "train_loss": running / max(1, seen),
            "val_accuracy": float(accuracy_score(y, preds)),
            "val_macro_f1": macro_f1(y, preds),
            "epoch_seconds": time.time() - epoch_start,
            "images_per_second": seen / max(1e-6, time.time() - epoch_start),
        }
        logger.log(row)
        state["history"].append(row)
        state["epoch"] = epoch + 1
        if row["val_macro_f1"] > state["best_f1"] + 1e-5:
            state.update(best_f1=row["val_macro_f1"], best_epoch=epoch + 1, stale=0)
            torch.save(model.state_dict(), run_dir / "best.pt")
        else:
            state["stale"] += 1
        torch.save(
            {
                "model": model.state_dict(),
                "optimizer": optimizer.state_dict(),
                "scheduler": scheduler.state_dict(),
                "scaler": scaler.state_dict(),
                "state": state,
                "rng": {
                    "torch": torch.get_rng_state(),
                    "numpy": np.random.get_state(),
                    "python": random.getstate(),
                },
            },
            last,
        )
        log.info(
            "%s epoch %d: %s",
            run_dir.name,
            epoch + 1,
            {k: round(v, 4) if isinstance(v, float) else v for k, v in row.items()},
        )

    model.load_state_dict(torch.load(run_dir / "best.pt", map_location=device, weights_only=True))
    metrics = evaluate_run(config, model, device, amp, val, test, run_dir)
    metrics.update(
        run_id=run_dir.name,
        config=config,
        best_epoch=state["best_epoch"],
        history=state["history"],
        train_minutes=(time.time() - started) / 60,
        device=str(device),
        versions={"torch": torch.__version__, "python": sys.version.split()[0]},
    )
    write_json(run_dir / "metrics.json", metrics)
    return metrics


def _eval_sets(config: dict, val: pd.DataFrame, test: pd.DataFrame) -> dict[str, tuple[pd.DataFrame, object]]:
    """Evaluation sets: val/test, background-swapped val/test, PlantDoc and GB field photos (when present)."""
    size = config["data"]["img_size"]
    sets: dict[str, tuple[pd.DataFrame, object]] = {"val": (val, None), "test": (test, None)}
    if not config["data"].get("synthetic") and "seg_path" in test:
        for name, frame in (("bgswap_val", val), ("bgswap_test", test)):
            sets[name] = (frame, BackgroundRandomizer(frame.seg_path.tolist(), None, p=1.0, seed=12345))
    if not config["data"].get("synthetic"):
        from cropdoc.research.common import field_frame, plantdoc_frame

        plantdoc = plantdoc_frame()
        if len(plantdoc):
            sets["plantdoc"] = (plantdoc, None)
        field = field_frame()
        if len(field):
            sets["field"] = (field, None)
    return {k: (v[0], v[1], size) for k, v in sets.items()}


def evaluate_run(config, model, device, amp, val, test, run_dir: Path) -> dict:
    results: dict = {"sets": {}}
    logits_by_set = {}
    for name, (frame, image_fn, size) in _eval_sets(config, val, test).items():
        loader = DataLoader(
            ManifestDataset(frame, eval_transform(crop=size), image_fn=image_fn),
            batch_size=config["train"]["batch_size"] * 2,
            num_workers=config["data"]["num_workers"],
        )
        logits, labels = predict_logits(model, loader, device, amp)
        logits_by_set[name] = (logits, labels)
        np.savez_compressed(run_dir / f"logits_{name}.npz", logits=logits.astype(np.float16), labels=labels)
    temperature = fit_temperature(*logits_by_set["val"])
    results["temperature"] = temperature
    for name, (logits, labels) in logits_by_set.items():
        preds = logits.argmax(1)
        entry = {
            "n": int(len(labels)),
            "accuracy": float(accuracy_score(labels, preds)),
            "macro_f1": macro_f1(labels, preds),
            "ece": expected_calibration_error(softmax(logits / temperature), labels),
        }
        if name in ("plantdoc", "field"):
            from cropdoc.research.common import crop_hint_predictions

            entry["crop_hint_accuracy"] = float((crop_hint_predictions(logits, labels) == labels).mean())
        results["sets"][name] = entry
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--config", action="append", default=[], help="experiment YAML (repeatable)")
    parser.add_argument("overrides", nargs="*", help="key.sub=value overrides")
    args = parser.parse_args(argv)
    config = load_config(*args.config, overrides=args.overrides)
    runs_dir = Path(config["output"]["runs_dir"])
    runs_dir = runs_dir if runs_dir.is_absolute() else paths.ROOT / runs_dir
    metrics = train_run(config, runs_dir / run_id(config))
    log.info("done: %s", {k: v for k, v in metrics["sets"].items()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
