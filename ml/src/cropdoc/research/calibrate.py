"""Calibration of the deployed model on lab and real-world photos (``make calibrate``).

ECE before/after temperature scaling (temperature fitted on validation only), reliability bins,
and the selective-prediction curve (coverage vs accuracy when the app abstains below a threshold).
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from cropdoc import paths  # noqa: E402
from cropdoc.calibration import expected_calibration_error, reliability_bins, selective_curve  # noqa: E402
from cropdoc.research.common import plantdoc_frame, softmax  # noqa: E402
from cropdoc.research.shift_eval import cached_logits  # noqa: E402
from cropdoc.utils import read_json, write_json  # noqa: E402

OUT = paths.RESULTS / "calibration"


def summarize(logits: np.ndarray, labels: np.ndarray, temperature: float) -> dict:
    raw, cal = softmax(logits), softmax(logits, temperature)
    confidence, correct = cal.max(1), cal.argmax(1) == labels
    return {
        "n": int(len(labels)),
        "ece_before": expected_calibration_error(raw, labels),
        "ece_after": expected_calibration_error(cal, labels),
        "mean_confidence": float(confidence.mean()),
        "accuracy": float(correct.mean()),
        "reliability": reliability_bins(cal, labels),
        "selective": selective_curve(confidence, correct, np.round(np.arange(0.0, 1.0, 0.05), 2)),
    }


def main() -> int:
    calibration = read_json(paths.MODELS_ACTIVE / "calibration.json")
    temperature = calibration["temperature"]
    lab = np.load(paths.CACHE / "quick_logits.npz")
    plantdoc = plantdoc_frame()
    pd_logits = cached_logits("plantdoc", plantdoc)
    test = summarize(lab["test"], lab["y_test"], temperature)
    field = summarize(pd_logits, plantdoc.label.to_numpy(), temperature)

    OUT.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2))
    for name, data in (("Lab test (PlantVillage)", test), ("Real-world (PlantDoc)", field)):
        bins = [b for b in data["reliability"] if b["count"]]
        axes[0].plot([b["confidence"] for b in bins], [b["accuracy"] for b in bins], marker="o", label=name)
        sel = [s for s in data["selective"] if s["accuracy"] is not None]
        axes[1].plot([s["coverage"] for s in sel], [s["accuracy"] for s in sel], marker=".", label=name)
    axes[0].plot([0, 1], [0, 1], "k--", lw=1, label="perfect calibration")
    axes[0].set(xlabel="confidence (after temperature)", ylabel="accuracy", title="Reliability diagram")
    axes[1].set(
        xlabel="coverage (share of photos answered)",
        ylabel="accuracy on answered photos",
        title="Selective prediction",
    )
    for ax in axes:
        ax.legend(fontsize=8)
        ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUT / "reliability.png", dpi=150)

    write_json(
        OUT / "calibration_summary.json",
        {
            "temperature": temperature,
            "fitted_on": calibration.get("fitted_on"),
            "test": {k: test[k] for k in ("n", "ece_before", "ece_after", "mean_confidence", "accuracy")},
            "plantdoc": {
                k: field[k] for k in ("n", "ece_before", "ece_after", "mean_confidence", "accuracy")
            },
            "reliability_test": test["reliability"],
            "reliability_plantdoc": field["reliability"],
            "selective_test": test["selective"],
            "selective_plantdoc": field["selective"],
            "figure": "results/calibration/reliability.png",
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
