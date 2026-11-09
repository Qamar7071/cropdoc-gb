"""Train the quick CPU model and install it into models/active/ (``make train``).

Every number written to model_card.json is measured here on the group-aware split:
validation for model selection / temperature / thresholds, the test split once at the end.

    python scripts/train_quick.py                    # full recipe (~30-40 min on 4 CPU cores)
    python scripts/train_quick.py --finetune-epochs 0  # linear probe only (~2 min after embeddings)
"""

from __future__ import annotations

import argparse
import shutil
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "ml" / "src"), str(ROOT / "backend")]

import numpy as np  # noqa: E402
import torch  # noqa: E402

from cropdoc import paths  # noqa: E402
from cropdoc.calibration import (  # noqa: E402
    expected_calibration_error,
    fit_temperature,
    negative_log_likelihood,
    reliability_bins,
    softmax,
    threshold_for_accuracy,
)
from cropdoc.data.classes import CLASS_IDS, classes_json  # noqa: E402
from cropdoc.embeddings import compute_embeddings  # noqa: E402
from cropdoc.quick import (  # noqa: E402
    balanced_subset,
    build_stage1_model,
    classification_metrics,
    export_onnx,
    finetune_tail,
    load_split,
    onnx_outputs,
    per_class_table,
    train_linear_probe,
)
from cropdoc.utils import get_logger, read_json, seed_everything, sha256_file, write_json  # noqa: E402

log = get_logger("train_quick")
ARCH = "mobilenetv3_large_100"
OUT = paths.RESULTS / "quick_model"


def energy(logits: np.ndarray) -> np.ndarray:
    """Energy score −logsumexp(logits): higher means 'less like the training data'."""
    peak = logits.max(axis=1, keepdims=True)
    return -(peak[:, 0] + np.log(np.exp(logits - peak).sum(axis=1)))


def parity_check(model, onnx_path: Path, frame) -> dict:
    """Compare PyTorch and ONNX Runtime outputs (logits and CAMs) on real test images."""
    import onnxruntime as ort

    from cropdoc.data.datasets import ManifestDataset
    from cropdoc.data.transforms import eval_transform

    batch = torch.stack([ManifestDataset(frame, eval_transform())[i][0] for i in range(len(frame))])
    model = model.eval().to(memory_format=torch.contiguous_format)
    with torch.inference_mode():
        t_logits, t_cams = model.forward_with_cams(batch)
    session = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    o_logits, o_cams = session.run(["logits", "cams"], {"image": batch.numpy()})
    return {
        "n_images": len(frame),
        "max_abs_diff_logits": float(np.abs(t_logits.numpy() - o_logits).max()),
        "max_abs_diff_cams": float(np.abs(t_cams.numpy() - o_cams).max()),
        "same_top1": bool((t_logits.numpy().argmax(1) == o_logits.argmax(1)).all()),
        "tolerance": 1e-3,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--finetune-epochs", type=int, default=3)
    parser.add_argument("--per-class", type=int, default=300, help="fine-tune subset size per class")
    parser.add_argument("--tail-blocks", type=int, default=3)
    parser.add_argument("--max-minutes", type=float, default=45.0, help="time budget for the fine-tune")
    parser.add_argument(
        "--target-accuracy", type=float, default=0.99, help="selective accuracy for 'confident'"
    )
    parser.add_argument(
        "--energy-tpr", type=float, default=0.99, help="share of val photos accepted by energy"
    )
    args = parser.parse_args()

    seed_everything(args.seed)
    torch.set_num_threads(4)
    t0 = time.time()
    frame = load_split("group_aware")
    train, val, test = (frame[frame.split == s].reset_index(drop=True) for s in ("train", "val", "test"))
    log.info("split sizes train=%d val=%d test=%d", len(train), len(val), len(test))

    # ---- stage 1: linear probe on frozen pretrained features (cached embeddings)
    embeddings = compute_embeddings(frame[["path"]], ARCH)
    index = {s: np.flatnonzero(frame.split.to_numpy() == s) for s in ("train", "val", "test")}
    probe = train_linear_probe(
        embeddings[index["train"]],
        train.label.to_numpy(),
        embeddings[index["val"]],
        val.label.to_numpy(),
        num_classes=len(CLASS_IDS),
        seed=args.seed,
    )
    log.info("stage 1 (linear probe) val: %s after %d epochs", probe.val_metrics, probe.epochs)
    stage1_seconds = time.time() - t0

    # ---- stage 2: brief fine-tune of the last blocks on a class-balanced subset
    model = build_stage1_model(probe, ARCH)
    candidates = {"stage1_linear_probe": (probe.val_metrics, None)}
    history: list[dict] = []
    if args.finetune_epochs > 0:
        subset = balanced_subset(train, args.per_class, args.seed)
        log.info("stage 2 fine-tune on %d images (≤%d per class)", len(subset), args.per_class)
        tuned, history = finetune_tail(
            build_stage1_model(probe, ARCH),
            subset,
            val,
            epochs=args.finetune_epochs,
            tail_blocks=args.tail_blocks,
            seed=args.seed,
            max_minutes=args.max_minutes,
        )
        best = max(history, key=lambda h: h["val_macro_f1"])
        candidates["stage2_finetune"] = (
            {"accuracy": best["val_accuracy"], "macro_f1": best["val_macro_f1"]},
            tuned,
        )
    selected = max(candidates, key=lambda k: candidates[k][0]["macro_f1"])
    if candidates[selected][1] is not None:
        model = candidates[selected][1]
    log.info("selected %s by validation macro-F1", selected)

    # ---- export + parity
    work = paths.CACHE / "quick_export"
    onnx_path = export_onnx(model, work / "model.onnx")
    parity = parity_check(model, onnx_path, test.sample(16, random_state=args.seed).reset_index(drop=True))
    log.info("parity: %s", parity)
    if not (parity["same_top1"] and parity["max_abs_diff_logits"] < parity["tolerance"]):
        raise RuntimeError(f"ONNX parity failed: {parity}")

    # ---- calibration + thresholds on validation (ONNX logits = deployed artifact)
    val_logits = onnx_outputs(onnx_path, val)
    y_val = val.label.to_numpy()
    temperature = fit_temperature(val_logits, y_val)
    val_probs = softmax(val_logits / temperature)
    conf_choice = threshold_for_accuracy(val_probs.max(1), val_probs.argmax(1) == y_val, args.target_accuracy)
    max_energy = float(np.quantile(energy(val_logits), args.energy_tpr))

    # ---- final test evaluation (once)
    test_logits = onnx_outputs(onnx_path, test)
    y_test = test.label.to_numpy()
    test_probs_raw, test_probs = softmax(test_logits), softmax(test_logits / temperature)
    test_metrics = classification_metrics(y_test, test_logits.argmax(1))
    test_metrics.update(
        ece_uncalibrated=expected_calibration_error(test_probs_raw, y_test),
        ece_calibrated=expected_calibration_error(test_probs, y_test),
        nll_uncalibrated=negative_log_likelihood(test_logits, y_test),
        nll_calibrated=negative_log_likelihood(test_logits, y_test, temperature),
    )
    keep = test_probs.max(1) >= conf_choice["threshold"]
    accepted_e = energy(test_logits) <= max_energy
    val_metrics = classification_metrics(y_val, val_logits.argmax(1))
    total_minutes = (time.time() - t0) / 60
    log.info("TEST %s", test_metrics)

    # ---- write results (source of every number shown in the app)
    OUT.mkdir(parents=True, exist_ok=True)
    per_class_table(y_test, test_logits.argmax(1)).to_csv(OUT / "per_class_test.csv", index=False)
    np.savez_compressed(
        paths.CACHE / "quick_logits.npz", val=val_logits, test=test_logits, y_val=y_val, y_test=y_test
    )
    split_manifest = read_json(paths.SPLITS / "manifest.json")
    created = datetime.now(UTC).isoformat(timespec="seconds")
    version = f"quick-mbv3l-{created[:10]}"
    metrics = {
        "model_version": version,
        "split": "group_aware",
        "split_sha256": split_manifest["splits"]["group_aware"]["sha256_csv"],
        "test": test_metrics,
        "val": val_metrics,
        "candidates_val": {k: v[0] for k, v in candidates.items()},
        "selected": selected,
        "finetune_history": history,
        "temperature": temperature,
        "thresholds": {
            "min_confidence": conf_choice["threshold"],
            "val_coverage_at_threshold": conf_choice["coverage"],
            "val_accuracy_at_threshold": conf_choice["accuracy"],
            "target_reached": conf_choice["reached"],
            "max_energy": max_energy,
            "energy_val_acceptance": args.energy_tpr,
            "test_coverage_confident": float(keep.mean()),
            "test_accuracy_confident": float((test_probs.argmax(1) == y_test)[keep].mean())
            if keep.any()
            else None,
            "test_energy_acceptance": float(accepted_e.mean()),
        },
        "reliability_test_calibrated": reliability_bins(test_probs, y_test),
        "reliability_test_uncalibrated": reliability_bins(test_probs_raw, y_test),
        "parity": parity,
        "timing_minutes": {"stage1": stage1_seconds / 60, "total": total_minutes},
        "hardware": "CPU only (4 cores), no GPU",
        "created_utc": created,
    }
    write_json(OUT / "metrics.json", metrics)
    write_json(paths.RESULTS / "export" / "parity.json", parity)

    active = paths.MODELS_ACTIVE
    active.mkdir(parents=True, exist_ok=True)
    shutil.copy(onnx_path, active / "model.onnx")
    write_json(active / "classes.json", classes_json())
    write_json(
        active / "calibration.json",
        {
            "temperature": temperature,
            "fitted_on": "validation split (group-aware), ONNX logits",
            "thresholds": {
                "min_confidence": conf_choice["threshold"],
                "max_energy": max_energy,
                "provisional": True,
                "source": (
                    f"validation: lowest confidence with ≥{args.target_accuracy:.0%} accuracy on kept photos; "
                    f"energy accepts {args.energy_tpr:.0%} of validation photos. Provisional until Milestone 2 "
                    "evaluates them on real out-of-distribution images."
                ),
            },
        },
    )
    write_json(
        active / "model_card.json",
        {
            "model_version": version,
            "name": "CropDoc GB quick model",
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
                "recipe": "stage 1: linear head on frozen features (full train split); "
                f"stage 2: fine-tune last {args.tail_blocks} blocks + head for ≤{args.finetune_epochs} epochs on a "
                f"class-balanced subset (≤{args.per_class} photos/class) with standard augmentation",
                "selected": selected,
                "seed": args.seed,
                "hardware": "CPU only (4 cores)",
                "minutes": round(total_minutes, 1),
            },
            "data": {
                "dataset": "PlantVillage (colour photos, lab conditions)",
                "split": "group-aware (photos of the same leaf never cross splits)",
                "split_sha256": metrics["split_sha256"],
                "sizes": {"train": len(train), "val": len(val), "test": len(test)},
                "source": split_manifest.get("data_sources", {}).get("plantvillage", {}),
            },
            "metrics": {
                "test_accuracy": test_metrics["accuracy"],
                "test_macro_f1": test_metrics["macro_f1"],
                "test_n": test_metrics["n"],
                "test_ece_calibrated": test_metrics["ece_calibrated"],
                "val_accuracy": val_metrics["accuracy"],
                "val_macro_f1": val_metrics["macro_f1"],
                "source": "results/quick_model/metrics.json",
            },
            "calibration": {"temperature": temperature, "fitted_on": "validation"},
            "intended_use": "General guidance for farmers and students; not a diagnosis.",
            "limitations": [
                "Trained only on lab photos (plain backgrounds); accuracy on real field photos is lower "
                "(see Field Intelligence).",
                "Covers only the 38 PlantVillage classes (14 crops). Other crops, e.g. apricot, are unsupported.",
                "Quick CPU model; a stronger model from the Colab sweep replaces it only if it scores better.",
            ],
            "onnx_sha256": sha256_file(active / "model.onnx"),
            "created_utc": created,
        },
    )
    log.info("installed model %s into %s (%.1f min)", version, active, total_minutes)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
