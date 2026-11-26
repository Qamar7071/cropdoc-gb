"""Field-robust model v2: learn from lab photos AND real-world photos (``make train-field``).

Why: model v1 learned from PlantVillage lab photos only. It is ~98% correct on lab test photos but
~21% on real-world web photos (results/shift/plantdoc_gap.json). Two well-known fixes, measured here:
  1. show the model real-world photos while training (PlantDoc, its own train split), and
  2. background randomization: paste lab leaves onto random textures so that the plain lab background
     stops being a shortcut and the model must look at the leaf.

Rules fixed BEFORE looking at any test result (docs/decisions.md, D22):
  * PlantDoc gets its own group-aware split (near-duplicate photos never cross splits): 60/15/25.
  * Model selection, temperature and thresholds use validation photos only (lab val + field val).
  * Lab test and field test are evaluated once at the end, for v1 and v2 with the same code.
  * v2 replaces v1 only if: field-test macro-F1 improves by >= 5 points, lab-test macro-F1 drops by at
    most 1 point, and at most 5% of non-leaf photos are answered "confident".

Run:  python -m cropdoc.field_model            (≈1 h on 4 CPU cores)
      python -m cropdoc.field_model --epochs 1 --per-class 20 --no-install   (quick smoke run)
"""

from __future__ import annotations

import argparse
import gzip
import io
import math
import shutil
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import confusion_matrix, precision_recall_fscore_support
from sklearn.model_selection import StratifiedGroupKFold
from torch import nn
from torch.utils.data import DataLoader, Dataset

from cropdoc import paths
from cropdoc.calibration import expected_calibration_error, fit_temperature, threshold_for_accuracy
from cropdoc.data.background import BackgroundRandomizer
from cropdoc.data.classes import CLASS_IDS, classes_json
from cropdoc.data.datasets import load_rgb
from cropdoc.data.dedup import UnionFind, hamming_min_dihedral, hash_files
from cropdoc.data.manifest import _relative, absolute
from cropdoc.data.split import split_sha256
from cropdoc.data.transforms import train_transform
from cropdoc.embeddings import compute_embeddings, l2_normalize
from cropdoc.models import CamNet
from cropdoc.quick import (
    balanced_subset,
    build_stage1_model,
    export_onnx,
    load_split,
    onnx_outputs,
    torch_logits,
)
from cropdoc.research.common import crop_hint_predictions, energy, imagenet_ood_frame, plantdoc_frame, softmax
from cropdoc.research.fewshot import train_head
from cropdoc.utils import get_logger, read_json, seed_everything, sha256_file, worker_init_fn, write_json

log = get_logger("field_model")
ARCH = "mobilenetv3_large_100"
OUT = paths.RESULTS / "field_model"
SPLIT_NAME = "plantdoc_group_aware"
NEAR_DUPLICATE_COSINE = 0.95
# pre-registered (D22)
TARGET_ACCURACY = 0.95
ENERGY_ACCEPT = 0.95
PROMOTE_MIN_FIELD_GAIN = 0.05
PROMOTE_MAX_LAB_DROP = 0.01
PROMOTE_MAX_NONLEAF_CONFIDENT = 0.05


# ============================================================================ data
def build_plantdoc_split(seed: int = 42) -> pd.DataFrame:
    """PlantDoc photos with a group-aware 60/15/25 split; written once to ml/splits and reused after."""
    target = paths.SPLITS / f"{SPLIT_NAME}.csv.gz"
    if target.exists():
        with gzip.open(target, "rb") as fh:
            return pd.read_csv(io.BytesIO(fh.read()))
    frame = plantdoc_frame().reset_index(drop=True)
    log.info("PlantDoc: %d readable photos in %d classes", len(frame), frame.class_id.nunique())
    # near-duplicates: embedding cosine (any class) ∪ identical pHash under rotation/flip
    uf = UnionFind(len(frame))
    emb = l2_normalize(compute_embeddings(frame[["path"]], ARCH))
    sims = emb @ emb.T
    np.fill_diagonal(sims, 0)
    for i, j in zip(*np.nonzero(np.triu(sims >= NEAR_DUPLICATE_COSINE)), strict=True):
        uf.union(int(i), int(j))
    hashes = hash_files([Path(p) for p in frame.path])
    dist = hamming_min_dihedral(hashes, hashes)
    np.fill_diagonal(dist, 64)
    for i, j in zip(*np.nonzero(np.triu(dist == 0)), strict=True):
        uf.union(int(i), int(j))
    groups = np.array([uf.find(i) for i in range(len(frame))])
    folds = np.empty(len(frame), dtype=int)
    splitter = StratifiedGroupKFold(n_splits=20, shuffle=True, random_state=seed)
    for fold, (_, idx) in enumerate(splitter.split(frame, frame.label, groups)):
        folds[idx] = fold
    split = np.where(folds < 5, "test", np.where(folds < 8, "val", "train"))  # 25% / 15% / 60%
    out = pd.DataFrame(
        {
            "path": [_relative(Path(p)) for p in frame.path],
            "folder": frame.folder,
            "class_id": frame.class_id,
            "label": frame.label,
            "group": groups,
            "plantdoc_split": frame.split,
            "split": split,
        }
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(target, "wb") as fh:
        fh.write(out.to_csv(index=False).encode())
    manifest = read_json(paths.SPLITS / "manifest.json")
    manifest.setdefault("splits", {})[SPLIT_NAME] = {
        "sha256_csv": split_sha256(out),
        "method": "StratifiedGroupKFold(20): 5 test, 3 val, 12 train; groups = embedding cosine >= "
        f"{NEAR_DUPLICATE_COSINE} ∪ identical dihedral pHash",
        "sizes": {s: int((out.split == s).sum()) for s in ("train", "val", "test")},
        "near_duplicate_groups_with_more_than_one_photo": int((pd.Series(groups).value_counts() > 1).sum()),
        "seed": seed,
    }
    write_json(paths.SPLITS / "manifest.json", manifest)
    log.info("PlantDoc split: %s", manifest["splits"][SPLIT_NAME]["sizes"])
    return out


def class_balance(lab: pd.DataFrame, field: pd.DataFrame) -> dict:
    """Photos per class and split in both datasets (the 'is the data balanced?' audit)."""
    rows = []
    for class_id in CLASS_IDS:
        row = {"class_id": class_id}
        for name, frame in (("lab", lab), ("field", field)):
            for s in ("train", "val", "test"):
                row[f"{name}_{s}"] = int(((frame.class_id == class_id) & (frame.split == s)).sum())
        rows.append(row)
    table = pd.DataFrame(rows)
    report = {}
    for name in ("lab", "field"):
        counts = table[f"{name}_train"]
        present = counts[counts > 0]
        report[name] = {
            "classes_present_in_train": int((counts > 0).sum()),
            "train_min": int(present.min()) if len(present) else 0,
            "train_max": int(present.max()) if len(present) else 0,
            "imbalance_ratio_max_over_min": float(present.max() / present.min()) if len(present) else None,
            "classes_missing": [c for c, n in zip(table.class_id, counts, strict=True) if n == 0],
        }
    report["per_class"] = rows
    report["note"] = (
        "Lab = PlantVillage group-aware split; field = PlantDoc group-aware split (web photos, not GB photos). "
        "Training uses a class-balanced lab subset and oversamples field photos to counter the imbalance."
    )
    return report


class MixedDataset(Dataset):
    """Lab photos (background randomization + standard augmentation) and field photos (strong augmentation)."""

    def __init__(self, lab: pd.DataFrame, field: pd.DataFrame, field_repeat: int, bg_p: float, seed: int):
        self.items = [(p, int(y), "lab") for p, y in zip(lab.path, lab.label, strict=True)]
        self.items += [
            (p, int(y), "field") for p, y in zip(field.path, field.label, strict=True)
        ] * field_repeat
        self.background = BackgroundRandomizer(
            list(lab.seg_path.fillna("")), background_dir=None, p=bg_p, seed=seed
        )
        self.lab_tf, self.field_tf = train_transform("standard"), train_transform("strong")

    def __len__(self) -> int:
        return len(self.items)

    def __getitem__(self, index: int):
        path, label, source = self.items[index]
        image = load_rgb(absolute(path))
        if source == "lab":
            image = self.background(image, index)
            return self.lab_tf(image), label, index
        return self.field_tf(image), label, index


def _freeze_frozen_bn(model: nn.Module) -> None:
    for module in model.modules():
        if isinstance(module, nn.BatchNorm2d) and not any(p.requires_grad for p in module.parameters()):
            module.eval()


def present_macro_f1(labels: np.ndarray, preds: np.ndarray) -> float:
    present = sorted(set(labels.tolist()))
    return float(
        precision_recall_fscore_support(labels, preds, labels=present, average="macro", zero_division=0)[2]
    )


def finetune_mixed(model: CamNet, data: MixedDataset, lab_val: pd.DataFrame, field_val: pd.DataFrame, args):
    """Fine-tune the last blocks + head; keep the epoch with the best mean(lab val, field val) macro-F1."""
    model.freeze_backbone(trainable_tail_blocks=args.tail_blocks)
    model.to(memory_format=torch.channels_last)
    tail = [p for p in model.backbone.parameters() if p.requires_grad]
    optimizer = torch.optim.AdamW(
        [{"params": tail, "lr": args.lr_tail}, {"params": model.fc.parameters(), "lr": args.lr_head}],
        weight_decay=1e-4,
    )
    loader = DataLoader(
        data,
        batch_size=32,
        shuffle=True,
        num_workers=3,
        worker_init_fn=worker_init_fn,
        generator=torch.Generator().manual_seed(args.seed),
        drop_last=True,
        persistent_workers=True,
    )
    total = args.epochs * len(loader)
    warmup = min(100, total // 10)
    schedule = torch.optim.lr_scheduler.LambdaLR(
        optimizer,
        lambda s: (
            (s + 1) / warmup
            if s < warmup
            else 0.5 * (1 + math.cos(math.pi * (s - warmup) / max(1, total - warmup)))
        ),
    )
    best, best_state, history, start = -1.0, None, [], time.time()
    for epoch in range(1, args.epochs + 1):
        model.train()
        _freeze_frozen_bn(model)
        running, seen, t_epoch = 0.0, 0, time.time()
        for step, (images, labels, _) in enumerate(loader):
            loss = nn.functional.cross_entropy(
                model(images.contiguous(memory_format=torch.channels_last)), labels, label_smoothing=0.05
            )
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            schedule.step()
            running, seen = running + loss.item() * len(labels), seen + len(labels)
            if step % 50 == 0:
                log.info(
                    "epoch %d step %d/%d loss %.4f (%.0f img/s)",
                    epoch,
                    step,
                    len(loader),
                    running / seen,
                    seen / (time.time() - t_epoch),
                )
        lab_f1 = present_macro_f1(lab_val.label.to_numpy(), torch_logits(model, lab_val).argmax(1))
        field_f1 = present_macro_f1(field_val.label.to_numpy(), torch_logits(model, field_val).argmax(1))
        score = (lab_f1 + field_f1) / 2
        history.append(
            {
                "epoch": epoch,
                "train_loss": running / seen,
                "val_lab_macro_f1": lab_f1,
                "val_field_macro_f1": field_f1,
                "val_score": score,
                "minutes": (time.time() - start) / 60,
            }
        )
        log.info("epoch %d: %s", epoch, history[-1])
        if score > best:
            best, best_state = score, {k: v.detach().clone() for k, v in model.state_dict().items()}
        if (time.time() - start) / 60 > args.max_minutes:
            log.info("time budget reached after epoch %d", epoch)
            break
    model.load_state_dict(best_state)
    return model.eval(), history


# ============================================================================ calibration + evaluation
def balanced_concat(lab: np.ndarray, field: np.ndarray) -> np.ndarray:
    """Repeat the (smaller) field set so both domains weigh the same."""
    repeat = max(1, round(len(lab) / max(1, len(field))))
    return np.concatenate([lab, *([field] * repeat)])


def calibrate(lab_logits, y_lab, field_logits, y_field) -> dict:
    """Temperature + 'not sure' + 'unsupported' thresholds from validation photos only (rule D22)."""
    logits = balanced_concat(lab_logits, field_logits)
    labels = balanced_concat(y_lab, y_field)
    temperature = fit_temperature(logits, labels)
    probs = softmax(logits, temperature)
    conf = threshold_for_accuracy(probs.max(1), probs.argmax(1) == labels, TARGET_ACCURACY)
    max_energy = float(
        max(np.quantile(energy(lab_logits), ENERGY_ACCEPT), np.quantile(energy(field_logits), ENERGY_ACCEPT))
    )
    return {
        "temperature": float(temperature),
        "min_confidence": float(conf["threshold"]),
        "max_energy": max_energy,
        "val_coverage_at_min_confidence": conf["coverage"],
        "val_accuracy_at_min_confidence": conf["accuracy"],
        "target_reached": conf["reached"],
        "rule": f"temperature + 'not sure' threshold on domain-balanced validation (lab = field weight), "
        f"lowest confidence with >= {TARGET_ACCURACY:.0%} accuracy on kept photos; 'unsupported' energy threshold "
        f"accepts >= {ENERGY_ACCEPT:.0%} of validation photos in each domain",
    }


def safety_net(logits, labels, cal) -> dict:
    probs = softmax(logits, cal["temperature"])
    correct = probs.argmax(1) == labels
    unsupported = energy(logits) > cal["max_energy"]
    low = ~unsupported & (probs.max(1) < cal["min_confidence"])
    confident = ~unsupported & ~low
    return {
        name: {
            "share": float(m.mean()),
            "n": int(m.sum()),
            "accuracy": float(correct[m].mean()) if m.any() else None,
        }
        for name, m in (("confident", confident), ("low_confidence", low), ("unsupported", unsupported))
    }


def evaluate(logits: np.ndarray, labels: np.ndarray, cal: dict) -> dict:
    preds = logits.argmax(1)
    present = sorted(set(labels.tolist()))
    p, r, f, s = precision_recall_fscore_support(labels, preds, labels=present, zero_division=0)
    return {
        "n": int(len(labels)),
        "n_classes": len(present),
        "accuracy": float((preds == labels).mean()),
        "macro_f1": float(f.mean()),
        "macro_precision": float(p.mean()),
        "macro_recall": float(r.mean()),
        "ece_calibrated": float(expected_calibration_error(softmax(logits, cal["temperature"]), labels)),
        "crop_hint_accuracy": float((crop_hint_predictions(logits, labels) == labels).mean()),
        "safety_net": safety_net(logits, labels, cal),
        "per_class": [
            {
                "class_id": CLASS_IDS[c],
                "precision": float(pp),
                "recall": float(rr),
                "f1": float(ff),
                "support": int(ss),
            }
            for c, pp, rr, ff, ss in zip(present, p, r, f, s, strict=True)
        ],
    }


def top_confusions(labels, preds, frame: pd.DataFrame, k: int = 15) -> list[dict]:
    pairs = pd.DataFrame({"true": labels, "pred": preds, "path": frame.path.to_numpy()})
    wrong = pairs[pairs.true != pairs.pred]
    out = []
    for (t, pr), group in wrong.groupby(["true", "pred"]):
        out.append(
            {
                "true": CLASS_IDS[t],
                "predicted": CLASS_IDS[pr],
                "count": int(len(group)),
                "examples": group.path.head(3).tolist(),
            }
        )
    return sorted(out, key=lambda row: -row["count"])[:k]


def save_confusion(labels, preds, name: str) -> None:
    present = sorted(set(labels.tolist()) | set(preds.tolist()))
    cm = confusion_matrix(labels, preds, labels=present)
    short = [CLASS_IDS[c].replace("___", ": ").replace("_", " ") for c in present]
    pd.DataFrame(cm, index=short, columns=short).to_csv(OUT / f"confusion_{name}.csv")
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    norm = cm / np.maximum(1, cm.sum(1, keepdims=True))
    fig, ax = plt.subplots(figsize=(12, 11), dpi=110)
    ax.imshow(norm, cmap="Greens", vmin=0, vmax=1)
    ax.set_xticks(range(len(short)), short, rotation=90, fontsize=6)
    ax.set_yticks(range(len(short)), short, fontsize=6)
    ax.set_xlabel("predicted")
    ax.set_ylabel("true")
    ax.set_title(f"Confusion matrix (row-normalized): {name}")
    fig.tight_layout()
    fig.savefig(OUT / f"confusion_{name}.png")
    plt.close(fig)


def paired_bootstrap(correct_a: np.ndarray, correct_b: np.ndarray, n: int = 2000, seed: int = 0) -> dict:
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(correct_a), size=(n, len(correct_a)))
    diffs = correct_b[idx].mean(1) - correct_a[idx].mean(1)
    return {
        "difference": float(correct_b.mean() - correct_a.mean()),
        "ci95": [float(np.quantile(diffs, 0.025)), float(np.quantile(diffs, 0.975))],
    }


def parity_check(model: CamNet, onnx_path: Path, frame: pd.DataFrame) -> dict:
    import onnxruntime as ort

    from cropdoc.data.datasets import ManifestDataset
    from cropdoc.data.transforms import eval_transform

    batch = torch.stack([ManifestDataset(frame, eval_transform())[i][0] for i in range(len(frame))])
    model = model.eval().to(memory_format=torch.contiguous_format)
    with torch.inference_mode():
        t_logits, t_cams = model.forward_with_cams(batch)
    o_logits, o_cams = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"]).run(
        ["logits", "cams"], {"image": batch.numpy()}
    )
    return {
        "n_images": len(frame),
        "max_abs_diff_logits": float(np.abs(t_logits.numpy() - o_logits).max()),
        "max_abs_diff_cams": float(np.abs(t_cams.numpy() - o_cams).max()),
        "same_top1": bool((t_logits.numpy().argmax(1) == o_logits.argmax(1)).all()),
        "tolerance": 1e-3,
    }


# ============================================================================ main
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--epochs", type=int, default=6)
    parser.add_argument(
        "--per-class", type=int, default=200, help="lab photos per class in each fine-tune run"
    )
    parser.add_argument(
        "--field-repeat", type=int, default=3, help="how often each field train photo is shown per epoch"
    )
    parser.add_argument("--tail-blocks", type=int, default=4)
    parser.add_argument(
        "--bg-p", type=float, default=0.6, help="share of lab photos with a randomized background"
    )
    parser.add_argument("--lr-tail", type=float, default=3e-4)
    parser.add_argument("--lr-head", type=float, default=1e-3)
    parser.add_argument(
        "--val-per-class", type=int, default=100, help="lab val photos per class for epoch selection"
    )
    parser.add_argument("--max-minutes", type=float, default=80.0)
    parser.add_argument("--no-install", action="store_true", help="never touch models/active (smoke runs)")
    args = parser.parse_args(argv)

    seed_everything(args.seed)
    torch.set_num_threads(4)
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)

    lab = load_split("group_aware")
    manifest = pd.read_csv(paths.CACHE / "manifest.csv", usecols=["path", "seg_path"])
    lab = lab.merge(manifest, on="path", how="left")
    field = build_plantdoc_split(args.seed)
    write_json(paths.RESULTS / "data_audit" / "class_balance.json", class_balance(lab, field))

    split = {
        f"{d}_{s}": f[f.split == s].reset_index(drop=True)
        for d, f in (("lab", lab), ("field", field))
        for s in ("train", "val", "test")
    }
    log.info("sizes: %s", {k: len(v) for k, v in split.items()})

    # ---- stage 1: weighted linear probe on frozen features (lab train + field train)
    lab_emb = compute_embeddings(lab[["path"]], ARCH)
    field_emb = compute_embeddings(field[["path"]].assign(path=[str(absolute(p)) for p in field.path]), ARCH)
    li = {s: np.flatnonzero(lab.split.to_numpy() == s) for s in ("train", "val", "test")}
    fi = {s: np.flatnonzero(field.split.to_numpy() == s) for s in ("train", "val", "test")}
    x = np.concatenate([lab_emb[li["train"]], field_emb[fi["train"]]])
    y = np.concatenate([split["lab_train"].label, split["field_train"].label]).astype(int)
    w = np.ones(len(y), dtype=np.float32)
    w[len(li["train"]) :] = 0.25 * len(li["train"]) / max(1, len(fi["train"]))
    head = train_head(x, y, w, args.seed)
    probe = type("Probe", (), {"weight": head.weight.detach().numpy(), "bias": head.bias.detach().numpy()})()
    model = build_stage1_model(probe, ARCH)

    # ---- stage 2: fine-tune on lab (background randomization) + field photos
    lab_sub = balanced_subset(split["lab_train"], args.per_class, args.seed)
    data = MixedDataset(lab_sub, split["field_train"], args.field_repeat, args.bg_p, args.seed)
    lab_val_sel = balanced_subset(split["lab_val"], args.val_per_class, args.seed)
    log.info(
        "fine-tune: %d lab + %d×%d field photos per epoch",
        len(lab_sub),
        len(split["field_train"]),
        args.field_repeat,
    )
    model, history = finetune_mixed(model, data, lab_val_sel, split["field_val"], args)

    # ---- export + parity
    onnx_path = export_onnx(model, paths.CACHE / "field_export" / "model.onnx")
    parity = parity_check(
        model, onnx_path, split["lab_test"].sample(8, random_state=1).reset_index(drop=True)
    )
    if not (parity["same_top1"] and parity["max_abs_diff_logits"] < parity["tolerance"]):
        raise RuntimeError(f"ONNX parity failed: {parity}")

    # ---- calibration on validation only (ONNX logits = the deployed artifact)
    logits = {k: onnx_outputs(onnx_path, split[k]) for k in ("lab_val", "field_val")}
    cal_v2 = calibrate(
        logits["lab_val"],
        split["lab_val"].label.to_numpy(),
        logits["field_val"],
        split["field_val"].label.to_numpy(),
    )
    log.info("v2 calibration: %s", cal_v2)

    # ---- one final evaluation: v1 (active model) and v2 on the same photos
    active_cal = read_json(paths.MODELS_ACTIVE / "calibration.json")
    cal_v1 = {
        "temperature": active_cal["temperature"],
        **{k: active_cal["thresholds"][k] for k in ("min_confidence", "max_energy")},
    }
    v1_path = paths.MODELS_ACTIVE / "model.onnx"
    ood = imagenet_ood_frame().assign(label=0)
    results = {}
    for name, path, cal in (("v1", v1_path, cal_v1), ("v2", onnx_path, cal_v2)):
        lab_test = onnx_outputs(path, split["lab_test"])
        field_test = onnx_outputs(path, split["field_test"])
        ood_logits = onnx_outputs(path, ood) if len(ood) else np.zeros((0, len(CLASS_IDS)))
        results[name] = {
            "model": str(path.relative_to(paths.ROOT)) if path.is_relative_to(paths.ROOT) else str(path),
            "calibration": {k: cal[k] for k in ("temperature", "min_confidence", "max_energy")},
            "lab_test": evaluate(lab_test, split["lab_test"].label.to_numpy(), cal),
            "field_test": evaluate(field_test, split["field_test"].label.to_numpy(), cal),
            "non_leaf_photos": {
                k: {"share": v["share"], "n": v["n"]}
                for k, v in safety_net(ood_logits, np.full(len(ood_logits), -1), cal).items()
            }
            if len(ood)
            else None,
        }
        results[name]["_preds"] = (lab_test.argmax(1), field_test.argmax(1))
    y_lab, y_field = split["lab_test"].label.to_numpy(), split["field_test"].label.to_numpy()
    for name in ("v1", "v2"):
        lab_pred, field_pred = results[name].pop("_preds")
        save_confusion(y_field, field_pred, f"field_test_{name}")
        save_confusion(y_lab, lab_pred, f"lab_test_{name}")
        results[name]["field_test_top_confusions"] = top_confusions(y_field, field_pred, split["field_test"])
        results[name]["_correct"] = (lab_pred == y_lab, field_pred == y_field)
    (v1_lab_c, v1_field_c), (v2_lab_c, v2_field_c) = (
        results["v1"].pop("_correct"),
        results["v2"].pop("_correct"),
    )

    gain = results["v2"]["field_test"]["macro_f1"] - results["v1"]["field_test"]["macro_f1"]
    drop = results["v1"]["lab_test"]["macro_f1"] - results["v2"]["lab_test"]["macro_f1"]
    nonleaf = (results["v2"]["non_leaf_photos"] or {}).get("confident", {}).get("share", 0.0)
    checks = {
        "field_macro_f1_gain": {
            "value": gain,
            "required": f">= {PROMOTE_MIN_FIELD_GAIN}",
            "ok": gain >= PROMOTE_MIN_FIELD_GAIN,
        },
        "lab_macro_f1_drop": {
            "value": drop,
            "required": f"<= {PROMOTE_MAX_LAB_DROP}",
            "ok": drop <= PROMOTE_MAX_LAB_DROP,
        },
        "non_leaf_confident_share": {
            "value": nonleaf,
            "required": f"<= {PROMOTE_MAX_NONLEAF_CONFIDENT}",
            "ok": nonleaf <= PROMOTE_MAX_NONLEAF_CONFIDENT,
        },
    }
    promote = all(c["ok"] for c in checks.values()) and not args.no_install
    created = datetime.now(UTC).isoformat(timespec="seconds")
    version = f"field-mbv3l-{created[:10]}"
    comparison = {
        "question": "Does training with real-world photos + background randomization close the lab→field gap?",
        "field_data": "PlantDoc (public web photos, own group-aware split; NOT Gilgit-Baltistan photos)",
        "split_sha256": read_json(paths.SPLITS / "manifest.json")["splits"][SPLIT_NAME]["sha256_csv"],
        "candidate_version": version,
        "v1": results["v1"],
        "v2": results["v2"],
        "field_accuracy_difference_v2_minus_v1": paired_bootstrap(v1_field_c, v2_field_c),
        "lab_accuracy_difference_v2_minus_v1": paired_bootstrap(v1_lab_c, v2_lab_c),
        "promotion_checks": checks,
        "promoted": promote,
        "training": {
            "args": vars(args),
            "history": history,
            "sizes": {k: len(v) for k, v in split.items()},
            "minutes": (time.time() - t0) / 60,
            "hardware": "CPU only (4 cores), no GPU",
        },
        "parity": parity,
        "created_utc": created,
    }
    write_json(OUT / "comparison.json", comparison)
    for name in ("v1", "v2"):
        for domain in ("lab_test", "field_test"):
            pd.DataFrame(results[name][domain]["per_class"]).to_csv(
                OUT / f"per_class_{domain}_{name}.csv", index=False
            )
    log.info("checks: %s → promote=%s", checks, promote)

    if promote:
        install(onnx_path, version, cal_v2, results["v2"], split, args, comparison)
    return 0


def install(onnx_path: Path, version: str, cal: dict, v2: dict, split: dict, args, comparison: dict) -> None:
    """Copy the ONNX model into models/active and regenerate calibration.json + model_card.json from results."""
    active = paths.MODELS_ACTIVE
    shutil.copy(onnx_path, active / "model.onnx")
    write_json(active / "classes.json", classes_json())
    write_json(
        active / "calibration.json",
        {
            "temperature": cal["temperature"],
            "fitted_on": "domain-balanced validation (lab val + field val), ONNX logits",
            "thresholds": {
                "min_confidence": cal["min_confidence"],
                "max_energy": cal["max_energy"],
                "provisional": False,
                "source": f"{cal['rule']} (results/field_model/comparison.json). GB field check pending.",
            },
        },
    )
    lab_t, field_t = v2["lab_test"], v2["field_test"]
    write_json(
        active / "model_card.json",
        {
            "model_version": version,
            "name": "CropDoc field-robust model (v2)",
            "architecture": "MobileNetV3-Large (ImageNet-pretrained, timm) + global-average-pool + linear head",
            "num_classes": len(CLASS_IDS),
            "input": "RGB photo, resized to 256 px (shorter side), centre-cropped to 224×224",
            "preprocessing": {
                "resize": 256,
                "crop": 224,
                "mean": [0.485, 0.456, 0.406],
                "std": [0.229, 0.224, 0.225],
            },
            "training": {
                "recipe": "stage 1: weighted linear head on frozen features (lab train + field train); stage 2: fine-tune "
                f"last {args.tail_blocks} blocks + head for ≤{args.epochs} epochs on ≤{args.per_class} lab photos/class "
                f"(background randomization p={args.bg_p}) + field train photos ×{args.field_repeat} (strong augmentation); "
                "best epoch by mean(lab val, field val) macro-F1",
                "seed": args.seed,
                "hardware": "CPU only (4 cores)",
                "minutes": round(comparison["training"]["minutes"], 1),
            },
            "data": {
                "dataset": "PlantVillage (lab photos) + PlantDoc (real-world web photos)",
                "split": "group-aware for both (near-duplicate photos never cross splits)",
                "split_sha256": read_json(paths.SPLITS / "manifest.json")["splits"]["group_aware"][
                    "sha256_csv"
                ],
                "field_split_sha256": comparison["split_sha256"],
                "sizes": {
                    "train": len(split["lab_train"]),
                    "val": len(split["lab_val"]),
                    "test": len(split["lab_test"]),
                    "field_train": len(split["field_train"]),
                    "field_val": len(split["field_val"]),
                    "field_test": len(split["field_test"]),
                },
            },
            "metrics": {
                "test_accuracy": lab_t["accuracy"],
                "test_macro_f1": lab_t["macro_f1"],
                "test_n": lab_t["n"],
                "test_ece_calibrated": lab_t["ece_calibrated"],
                "field_test_accuracy": field_t["accuracy"],
                "field_test_macro_f1": field_t["macro_f1"],
                "field_test_n": field_t["n"],
                "field_test_crop_hint_accuracy": field_t["crop_hint_accuracy"],
                "source": "results/field_model/comparison.json",
            },
            "calibration": {"temperature": cal["temperature"], "fitted_on": "domain-balanced validation"},
            "intended_use": "General guidance for farmers and students; not a diagnosis.",
            "limitations": [
                "Field photos used for training and testing are public web photos (PlantDoc), not Gilgit-Baltistan or "
                "Pakistani field photos; accuracy on local photos is not measured yet (GB study PENDING).",
                "Covers only the 38 PlantVillage classes (14 crops). Wheat, rice, cotton, sugarcane, mango and apricot "
                "are not supported by the scanner.",
                "Real-world accuracy is still much lower than lab accuracy: treat answers as a hint and confirm with an expert.",
            ],
            "onnx_sha256": sha256_file(active / "model.onnx"),
            "created_utc": comparison["created_utc"],
        },
    )
    log.info("installed %s into %s", version, active)


if __name__ == "__main__":
    raise SystemExit(main())
