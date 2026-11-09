"""Promote a finished sweep run to models/active, ONLY if it beats the current model (``make promote RUN=<id>``).

Rule (CLAUDE.md rule 5): compare macro-F1 on the group-aware test split. If the candidate is better,
export it to ONNX (with the parity check), fit thresholds on validation with the Milestone-2 rule,
and regenerate model_card.json from the run's result files. Otherwise nothing changes.
"""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import UTC, datetime

import numpy as np
import torch

from cropdoc import paths
from cropdoc.calibration import softmax, threshold_for_accuracy
from cropdoc.data.classes import CLASS_IDS, classes_json
from cropdoc.models import build_model
from cropdoc.quick import export_onnx
from cropdoc.research.common import energy
from cropdoc.sweep import planned_runs
from cropdoc.utils import get_logger, sha256_file, write_json

log = get_logger("cropdoc.promote")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--run", required=True, help="run id (folder name in the runs directory)")
    parser.add_argument(
        "--force", action="store_true", help="promote even if not better (never used for releases)"
    )
    args = parser.parse_args(argv)
    run = next((r for r in planned_runs() if r["run_id"] == args.run and r["done"]), None)
    if run is None:
        raise SystemExit(f"no finished run {args.run}")
    metrics = json.loads((run["run_dir"] / "metrics.json").read_text())
    if metrics["config"]["data"]["split"] != "group_aware":
        raise SystemExit("only runs trained on the group-aware split can be promoted")
    candidate = metrics["sets"]["test"]["macro_f1"]
    current_card = json.loads((paths.MODELS_ACTIVE / "model_card.json").read_text())
    current = current_card["metrics"]["test_macro_f1"]
    log.info("candidate test macro-F1 %.4f vs current %.4f", candidate, current)
    if candidate <= current and not args.force:
        log.info("not promoted: the current model is as good or better")
        return 0

    model = build_model(metrics["config"]["model"]["arch"], len(CLASS_IDS), pretrained=False)
    model.load_state_dict(torch.load(run["run_dir"] / "best.pt", map_location="cpu", weights_only=True))
    work = paths.CACHE / "promote" / args.run
    onnx_path = export_onnx(model.eval(), work / "model.onnx")
    val = np.load(run["run_dir"] / "logits_val.npz")
    val_logits, y_val = val["logits"].astype(np.float32), val["labels"]
    temperature = metrics["temperature"]
    probs = softmax(val_logits / temperature)
    conf = threshold_for_accuracy(probs.max(1), probs.argmax(1) == y_val, 0.99)
    thresholds = {
        "min_confidence": conf["threshold"],
        "max_energy": float(np.quantile(energy(val_logits), 0.95)),
        "provisional": False,
        "source": f"validation of run {args.run} (Milestone-2 rule)",
    }

    backup = paths.MODELS_ACTIVE.parent / f"previous-{current_card.get('model_version', 'unknown')}"
    if not backup.exists():
        shutil.copytree(paths.MODELS_ACTIVE, backup)
    shutil.copy(onnx_path, paths.MODELS_ACTIVE / "model.onnx")
    write_json(paths.MODELS_ACTIVE / "classes.json", classes_json())
    write_json(
        paths.MODELS_ACTIVE / "calibration.json",
        {"temperature": temperature, "fitted_on": "validation", "thresholds": thresholds},
    )
    test = metrics["sets"]["test"]
    created = datetime.now(UTC).isoformat(timespec="seconds")
    write_json(
        paths.MODELS_ACTIVE / "model_card.json",
        {
            **{
                k: current_card[k]
                for k in ("name", "input", "preprocessing", "intended_use", "limitations")
                if k in current_card
            },
            "model_version": f"{run['experiment']}-{args.run}",
            "architecture": f"{metrics['config']['model']['arch']} + global-average-pool + linear head",
            "num_classes": len(CLASS_IDS),
            "training": {
                "recipe": f"sweep experiment {run['experiment']} (seed {run['seed']})",
                "hardware": metrics.get("device"),
            },
            "metrics": {
                "test_accuracy": test["accuracy"],
                "test_macro_f1": test["macro_f1"],
                "test_n": test["n"],
                "test_ece_calibrated": test["ece"],
                "source": f"runs/{args.run}/metrics.json (copied to results/promoted_model.json)",
            },
            "calibration": {"temperature": temperature, "fitted_on": "validation"},
            "onnx_sha256": sha256_file(paths.MODELS_ACTIVE / "model.onnx"),
            "created_utc": created,
        },
    )
    write_json(
        paths.RESULTS / "promoted_model.json",
        {
            "run_id": args.run,
            "experiment": run["experiment"],
            "previous": current_card,
            "metrics": metrics["sets"],
            "promoted_utc": created,
        },
    )
    log.info("promoted %s → models/active (previous model kept in %s)", args.run, backup)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
