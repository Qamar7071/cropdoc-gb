"""Aggregate finished sweep runs into a tidy table + plots + bootstrap CIs (``make eval``).

Reads every run's metrics.json and saved logits (no GPU needed) and writes:
  results/sweep/runs.csv      one row per (experiment, seed)
  results/sweep/summary.csv / summary.md / summary.json   mean ± std over seeds per experiment
  results/sweep/comparisons.json   pre-registered comparisons (docs/preregistration.md) with 95% CIs
  results/sweep/summary.png   lab test vs real-world accuracy per experiment (error bars = std)
Nothing is written while no run has finished (the docs then show PENDING).
"""

from __future__ import annotations

import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from cropdoc import paths  # noqa: E402
from cropdoc.stats import bootstrap_diff  # noqa: E402
from cropdoc.sweep import planned_runs  # noqa: E402
from cropdoc.utils import get_logger, write_json  # noqa: E402

log = get_logger("cropdoc.evaluate")
OUT = paths.RESULTS / "sweep"

# Pre-registered comparisons (identical list in docs/preregistration.md): (id, question, A, B, eval set, metric)
COMPARISONS = [
    ("H1-r18", "Leakage inflation (ResNet18)", "r18_std_naive", "r18_std", "test", "accuracy"),
    ("H1-mbv3", "Leakage inflation (MobileNetV3)", "mbv3_std_naive", "mbv3_std", "test", "accuracy"),
    ("H1-cnn", "Leakage inflation (SmallCNN)", "cnn_std_naive", "cnn_std", "test", "accuracy"),
    (
        "H3-r18",
        "Background randomization vs standard on real-world photos (ResNet18)",
        "r18_bgrand",
        "r18_std",
        "plantdoc",
        "accuracy",
    ),
    (
        "H3-mbv3",
        "Background randomization vs standard on real-world photos (MobileNetV3)",
        "mbv3_bgrand",
        "mbv3_std",
        "plantdoc",
        "accuracy",
    ),
    (
        "H4-r18",
        "Strong vs standard augmentation on real-world photos (ResNet18)",
        "r18_strong",
        "r18_std",
        "plantdoc",
        "accuracy",
    ),
    ("H5", "Pretrained vs from-scratch on real-world photos", "mbv3_std", "cnn_std", "plantdoc", "accuracy"),
]


def collect() -> pd.DataFrame:
    rows = []
    for r in planned_runs():
        if not r["done"]:
            continue
        metrics = json.loads((r["run_dir"] / "metrics.json").read_text())
        row = {
            "block": r["block"],
            "experiment": r["experiment"],
            "seed": r["seed"],
            "run_id": r["run_id"],
            "model": r["config"]["model"]["arch"],
            "aug": r["config"]["data"]["aug"],
            "split": r["config"]["data"]["split"],
            "class_balance": r["config"]["data"]["class_balance"],
            "best_epoch": metrics.get("best_epoch"),
            "train_minutes": metrics.get("train_minutes"),
        }
        for name, values in metrics["sets"].items():
            for key, value in values.items():
                if key != "n":
                    row[f"{name}_{key}"] = value
        rows.append(row)
    return pd.DataFrame(rows)


def per_image_correct(run_dir, eval_set: str) -> np.ndarray | None:
    path = run_dir / f"logits_{eval_set}.npz"
    if not path.exists():
        return None
    data = np.load(path)
    return (data["logits"].astype(np.float32).argmax(1) == data["labels"]).astype(np.float32)


def comparisons(runs: list[dict]) -> list[dict]:
    """Seed-averaged per-image correctness, then a paired bootstrap over images (same test photos)."""
    by_exp: dict[str, list] = {}
    for r in runs:
        if r["done"]:
            by_exp.setdefault(r["experiment"], []).append(r)
    out = []
    for cid, question, a, b, eval_set, _metric in COMPARISONS:
        if a not in by_exp or b not in by_exp:
            out.append({"id": cid, "question": question, "status": "pending"})
            continue
        ca = [per_image_correct(r["run_dir"], eval_set) for r in by_exp[a]]
        cb = [per_image_correct(r["run_dir"], eval_set) for r in by_exp[b]]
        if any(c is None for c in ca + cb):
            out.append({"id": cid, "question": question, "status": "pending"})
            continue
        paired = eval_set != "test" or (
            by_exp[a][0]["config"]["data"]["split"] == by_exp[b][0]["config"]["data"]["split"]
        )
        result = bootstrap_diff(
            np.mean(ca, axis=0), np.mean(cb, axis=0), paired=paired and len(ca[0]) == len(cb[0])
        )
        out.append(
            {
                "id": cid,
                "question": question,
                "a": a,
                "b": b,
                "eval_set": eval_set,
                "status": "ready",
                "seeds_a": len(ca),
                "seeds_b": len(cb),
                **result,
            }
        )
    return out


def main() -> int:
    table = collect()
    if table.empty:
        log.warning("PENDING: no finished sweep runs yet (run ml/notebooks/colab_run.ipynb)")
        return 0
    OUT.mkdir(parents=True, exist_ok=True)
    table.to_csv(OUT / "runs.csv", index=False)
    metric_cols = [c for c in table.columns if c.endswith(("_accuracy", "_macro_f1", "_ece"))]
    summary = table.groupby(["block", "experiment", "model", "aug", "split", "class_balance"])[
        metric_cols
    ].agg(["mean", "std"])
    summary.columns = [f"{a}_{b}" for a, b in summary.columns]
    summary = summary.reset_index()
    summary["seeds"] = table.groupby(["block", "experiment"]).size().values
    summary.to_csv(OUT / "summary.csv", index=False)

    def fmt(row, col):
        mean, std = row.get(f"{col}_mean"), row.get(f"{col}_std")
        return "—" if pd.isna(mean) else f"{mean * 100:.1f} ± {0 if pd.isna(std) else std * 100:.1f}"

    lines = [
        "| block | experiment | seeds | lab test acc (%) | bg-swap test acc (%) | PlantDoc acc (%) | PlantDoc macro-F1 (%) |",
        "|---|---|---|---|---|---|---|",
    ]
    for _, row in summary.iterrows():
        lines.append(
            f"| {row.block} | {row.experiment} | {row.seeds} | {fmt(row, 'test_accuracy')} | "
            f"{fmt(row, 'bgswap_test_accuracy')} | {fmt(row, 'plantdoc_accuracy')} | {fmt(row, 'plantdoc_macro_f1')} |"
        )
    (OUT / "summary.md").write_text("\n".join(lines) + "\n")
    comps = comparisons(planned_runs())
    write_json(OUT / "comparisons.json", comps)
    write_json(
        OUT / "summary.json",
        {
            "rows": json.loads(summary.to_json(orient="records")),
            "comparisons": comps,
            "table_markdown": "results/sweep/summary.md",
        },
    )

    fig, ax = plt.subplots(figsize=(max(6, len(summary) * 0.6), 4))
    x = np.arange(len(summary))
    for offset, col, label in (
        (-0.2, "test_accuracy", "lab test"),
        (0.2, "plantdoc_accuracy", "real-world (PlantDoc)"),
    ):
        if f"{col}_mean" in summary:
            ax.bar(
                x + offset,
                summary[f"{col}_mean"],
                0.4,
                yerr=summary[f"{col}_std"].fillna(0),
                capsize=3,
                label=label,
            )
    ax.set_xticks(x, summary.experiment, rotation=60, ha="right", fontsize=8)
    ax.set(ylabel="accuracy (mean ± std over seeds)", ylim=(0, 1), title="Experiment matrix")
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUT / "summary.png", dpi=150)
    log.info("aggregated %d runs into %s", len(table), OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
