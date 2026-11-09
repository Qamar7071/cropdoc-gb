"""Milestone-2 calibration of the app's decision thresholds (``make calibrate`` runs it after calibrate.py).

Rule (fixed in advance, uses validation data only):
  * temperature: unchanged (fitted on validation NLL during training);
  * "not sure" threshold: lowest calibrated confidence whose kept validation predictions reach 99% accuracy;
  * "unsupported" threshold: energy at the 95th percentile of validation photos (the standard 95%-TPR
    operating point: 5% of in-distribution photos are flagged, the rest are accepted).
Then the behaviour is *reported* (not tuned) on lab test, real-world PlantDoc and non-leaf photos, and
the thresholds are written into models/active/calibration.json for the web app.
"""

from __future__ import annotations

import numpy as np

from cropdoc import paths
from cropdoc.calibration import threshold_for_accuracy
from cropdoc.research.common import energy, imagenet_ood_frame, plantdoc_frame, softmax
from cropdoc.research.shift_eval import cached_logits, safety_net
from cropdoc.utils import read_json, write_json

ENERGY_TPR = 0.95
TARGET_ACCURACY = 0.99


def main() -> int:
    calibration_path = paths.MODELS_ACTIVE / "calibration.json"
    calibration = read_json(calibration_path)
    temperature = calibration["temperature"]
    lab = np.load(paths.CACHE / "quick_logits.npz")
    val_logits, y_val = lab["val"], lab["y_val"]
    val_probs = softmax(val_logits, temperature)
    conf = threshold_for_accuracy(val_probs.max(1), val_probs.argmax(1) == y_val, TARGET_ACCURACY)
    thresholds = {
        "min_confidence": conf["threshold"],
        "max_energy": float(np.quantile(energy(val_logits), ENERGY_TPR)),
    }

    plantdoc = plantdoc_frame()
    behaviour = {
        "lab_test": safety_net(lab["test"], lab["y_test"], temperature, thresholds),
        "plantdoc_real_world": safety_net(
            cached_logits("plantdoc", plantdoc), plantdoc.label.to_numpy(), temperature, thresholds
        ),
    }
    imagenet = imagenet_ood_frame()
    if len(imagenet):
        logits = cached_logits("imagenet_ood", imagenet)
        behaviour["non_leaf_photos"] = {
            k: {"share": v["share"], "n": v["n"]}
            for k, v in safety_net(logits, np.full(len(logits), -1), temperature, thresholds).items()
        }
    previous = calibration.get("thresholds", {})
    report = {
        "rule": {
            "min_confidence": f"lowest confidence with ≥{TARGET_ACCURACY:.0%} accuracy on kept validation photos",
            "max_energy": f"{ENERGY_TPR:.0%} of validation photos accepted (95%-TPR operating point)",
        },
        "thresholds": thresholds,
        "validation_coverage_at_min_confidence": conf["coverage"],
        "previous_thresholds": {k: previous.get(k) for k in ("min_confidence", "max_energy")},
        "behaviour": behaviour,
    }
    write_json(paths.RESULTS / "calibration" / "thresholds.json", report)
    calibration["thresholds"] = {
        **thresholds,
        "provisional": False,
        "source": "Milestone 2: chosen on validation data only (results/calibration/thresholds.json); behaviour on "
        "unseen diseases, non-leaf and real-world photos in results/ood/ood_summary.json. GB field check pending.",
    }
    write_json(calibration_path, calibration)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
