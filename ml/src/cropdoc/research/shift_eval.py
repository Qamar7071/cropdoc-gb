"""Lab → real-world gap of the deployed model (``make shift``).

* PlantDoc (public web photos of leaves in real settings, 28 classes mapped to PlantVillage):
  accuracy / macro-F1 vs the lab test photos of the same classes, the gain from a crop hint,
  calibration, what the app's safety thresholds do, and per-class recall.
* Gilgit-Baltistan field photos (data/field_test): the same report once photos exist; PENDING before.
"""

from __future__ import annotations

import numpy as np

from cropdoc import paths
from cropdoc.calibration import expected_calibration_error
from cropdoc.data.classes import CLASS_IDS
from cropdoc.data.dedup import hash_files
from cropdoc.research.common import (
    crop_hint_predictions,
    energy,
    field_frame,
    log,
    metrics_on_present_classes,
    onnx_outputs,
    plantdoc_frame,
    softmax,
)
from cropdoc.stats import bootstrap_ci, bootstrap_diff
from cropdoc.utils import read_json, sha256_file, write_json

MODEL = paths.MODELS_ACTIVE / "model.onnx"


def cached_logits(name: str, frame) -> np.ndarray:
    """ONNX logits for a frame, cached per model hash (other experiments reuse them)."""
    key = sha256_file(MODEL)[:12]
    cache = paths.CACHE / f"{name}_logits_{key}.npz"
    if cache.exists():
        stored = np.load(cache, allow_pickle=True)
        if list(stored["paths"]) == list(frame.path):
            return stored["logits"]
    logits, _ = onnx_outputs(MODEL, frame)
    np.savez_compressed(cache, logits=logits, paths=np.array(frame.path))
    return logits


def safety_net(logits: np.ndarray, labels: np.ndarray, temperature: float, thresholds: dict) -> dict:
    """What the app shows: share confident / not sure / unsupported, and accuracy of each group."""
    probs = softmax(logits, temperature)
    confidence = probs.max(1)
    correct = probs.argmax(1) == labels
    unsupported = energy(logits) > thresholds["max_energy"]
    low = ~unsupported & (confidence < thresholds["min_confidence"])
    confident = ~unsupported & ~low
    out = {}
    for name, mask in (("confident", confident), ("low_confidence", low), ("unsupported", unsupported)):
        out[name] = {
            "share": float(mask.mean()),
            "n": int(mask.sum()),
            "accuracy": float(correct[mask].mean()) if mask.any() else None,
        }
    return out


def gap_report(field_logits, field_labels, lab_logits, lab_labels, calibration: dict, dataset: str) -> dict:
    present = sorted(set(field_labels.tolist()))
    lab_mask = np.isin(lab_labels, present)
    lab_logits, lab_labels = lab_logits[lab_mask], lab_labels[lab_mask]
    temperature = calibration["temperature"]
    lab_correct = lab_logits.argmax(1) == lab_labels
    field_correct = field_logits.argmax(1) == field_labels
    hint_preds = crop_hint_predictions(field_logits, field_labels)

    per_class = []
    for label in present:
        lab_rows, field_rows = lab_labels == label, field_labels == label
        per_class.append(
            {
                "class_id": CLASS_IDS[label],
                "n_lab": int(lab_rows.sum()),
                "n_field": int(field_rows.sum()),
                "lab_recall": float(lab_correct[lab_rows].mean()) if lab_rows.any() else None,
                "field_recall": float(field_correct[field_rows].mean()),
            }
        )
    per_class.sort(key=lambda r: r["field_recall"] - (r["lab_recall"] or 0))
    return {
        "dataset": dataset,
        "model_version": read_json(paths.MODELS_ACTIVE / "model_card.json").get("model_version"),
        "classes_compared": len(present),
        "lab": {
            **metrics_on_present_classes(lab_labels, lab_logits.argmax(1)),
            "source": "PlantVillage group-aware test split, same classes",
        },
        "field": metrics_on_present_classes(field_labels, field_logits.argmax(1)),
        "field_crop_hint": metrics_on_present_classes(field_labels, hint_preds),
        "accuracy_drop": bootstrap_diff(lab_correct, field_correct),
        "field_accuracy_ci": bootstrap_ci(field_correct),
        "calibration": {
            "temperature": temperature,
            "lab_ece": expected_calibration_error(softmax(lab_logits, temperature), lab_labels),
            "field_ece": expected_calibration_error(softmax(field_logits, temperature), field_labels),
        },
        "safety_net": {
            "lab": safety_net(lab_logits, lab_labels, temperature, calibration["thresholds"]),
            "field": safety_net(field_logits, field_labels, temperature, calibration["thresholds"]),
        },
        "per_class": per_class,
    }


def main() -> int:
    calibration = read_json(paths.MODELS_ACTIVE / "calibration.json")
    lab = np.load(paths.CACHE / "quick_logits.npz")
    lab_logits, lab_labels = lab["test"], lab["y_test"]

    plantdoc = plantdoc_frame()
    log.info("PlantDoc: %d readable photos", len(plantdoc))
    logits = cached_logits("plantdoc", plantdoc)
    report = gap_report(
        logits,
        plantdoc.label.to_numpy(),
        lab_logits,
        lab_labels,
        calibration,
        "PlantDoc (public real-world web photos, train+test; NOT Gilgit-Baltistan photos)",
    )
    # cross-dataset contamination check: identical (rotation/flip-invariant) pHash with any PlantVillage photo
    pv_hashes = np.load(paths.CACHE / "phash_dihedral.npy").min(axis=1)
    pd_hashes = hash_files(
        [paths.PLANTDOC.parent / p if not p.startswith("/") else p for p in plantdoc.path]
    ).min(axis=1)
    report["contamination"] = {
        "plantdoc_photos_identical_to_plantvillage": int(np.isin(pd_hashes, pv_hashes).sum())
    }
    write_json(paths.RESULTS / "shift" / "plantdoc_gap.json", report)
    log.info(
        "PlantDoc: lab acc %.3f → field acc %.3f (crop hint %.3f)",
        report["lab"]["accuracy"],
        report["field"]["accuracy"],
        report["field_crop_hint"]["accuracy"],
    )

    field = field_frame()
    if field.empty:
        log.warning(
            "PENDING: no GB field photos in %s (see docs/field_collection_guide.md)", paths.FIELD_TEST
        )
    else:
        field_logits = cached_logits("field", field)
        write_json(
            paths.RESULTS / "shift" / "field_gap.json",
            gap_report(
                field_logits,
                field.label.to_numpy(),
                lab_logits,
                lab_labels,
                calibration,
                "Gilgit-Baltistan field photos (data/field_test)",
            ),
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
