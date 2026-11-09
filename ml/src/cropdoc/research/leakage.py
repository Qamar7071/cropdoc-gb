"""Leakage study: how much does a naive random split inflate accuracy? (``make leakage``)

Same models, same proportions (70/15/15); the only difference is whether photos of the same leaf
may land in both train and test. Models: frozen pretrained CNN features + linear head (3 seeds),
plus every baseline (classical LR/RF, tiny MLP on pixels, 1-NN). Also: within the naive test set,
accuracy on photos whose leaf-sibling is in train ("exposed") vs photos without one.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from cropdoc import baselines, paths
from cropdoc.data.classes import CLASS_IDS
from cropdoc.embeddings import compute_embeddings
from cropdoc.quick import train_linear_probe
from cropdoc.research.common import load_split, log
from cropdoc.stats import bootstrap_diff
from cropdoc.utils import read_json, write_json

ARCH = "mobilenetv3_large_100"
SEEDS = [0, 1, 2]


def probe(x_tr, y_tr, x_va, y_va, x_te, seed: int) -> np.ndarray:
    import torch

    result = train_linear_probe(x_tr, y_tr, x_va, y_va, num_classes=len(CLASS_IDS), seed=seed)
    layer = torch.nn.Linear(x_tr.shape[1], len(CLASS_IDS))
    with torch.no_grad():
        layer.weight.copy_(torch.from_numpy(result.weight))
        layer.bias.copy_(torch.from_numpy(result.bias))
        return layer(torch.from_numpy(x_te)).argmax(1).numpy()


def main() -> int:
    group, naive = load_split("group_aware"), load_split("naive")
    assert (group.path.to_numpy() == naive.path.to_numpy()).all(), "splits must list photos in the same order"
    y, groups = group.label.to_numpy(), group.group.to_numpy()
    embeddings = compute_embeddings(group[["path"]], ARCH)
    features, pixels = baselines.load_features(group)
    pixels = pixels.reshape(len(pixels), -1).astype(np.float32)

    rows, probe_correct = [], {}
    for split_name, frame in (("naive", naive), ("group_aware", group)):
        s = frame.split.to_numpy()
        tr, va, te = s == "train", s == "val", s == "test"
        for seed in SEEDS:
            preds = probe(embeddings[tr], y[tr], embeddings[va], y[va], embeddings[te], seed)
            probe_correct.setdefault(split_name, []).append(preds == y[te])
            rows.append(
                {
                    "model": "Frozen CNN features + linear head",
                    "split": split_name,
                    "seed": seed,
                    **baselines._scores(y[te], preds),
                }
            )
            log.info("%s probe seed %d: %s", split_name, seed, rows[-1])
        runners = [
            ("Classical features + logistic regression", baselines.logistic_regression, features, [0]),
            ("Classical features + random forest", baselines.random_forest, features, SEEDS),
            ("Tiny MLP (ANN) on 32x32 pixels", baselines.tiny_mlp, pixels, SEEDS),
            ("1-nearest-neighbour on CNN features", baselines.nearest_neighbour, embeddings, [0]),
        ]
        for name, fn, x, seeds in runners:
            for seed in seeds:
                rows.append(
                    {"model": name, "split": split_name, "seed": seed, **fn(x[tr], y[tr], x[te], y[te], seed)}
                )
                log.info("%s %s seed %d: %s", split_name, name, seed, rows[-1])

    table = pd.DataFrame(rows)
    summary = (
        table.groupby(["model", "split"])
        .agg(
            accuracy_mean=("accuracy", "mean"),
            accuracy_std=("accuracy", "std"),
            macro_f1_mean=("macro_f1", "mean"),
            macro_f1_std=("macro_f1", "std"),
            runs=("seed", "count"),
        )
        .fillna({"accuracy_std": 0.0, "macro_f1_std": 0.0})
        .reset_index()
    )
    (paths.RESULTS / "baselines").mkdir(parents=True, exist_ok=True)
    table.to_csv(paths.RESULTS / "baselines" / "runs.csv", index=False)
    summary.to_csv(paths.RESULTS / "baselines" / "summary.csv", index=False)
    write_json(
        paths.RESULTS / "baselines" / "baselines.json",
        {
            "description": "Test accuracy / macro-F1 on the naive and the group-aware split (mean ± std over seeds)",
            "rows": summary.to_dict("records"),
        },
    )

    # exposure analysis inside the naive test set (probe, seed 0)
    s = naive.split.to_numpy()
    train_groups = set(groups[s == "train"])
    exposed = np.array([g in train_groups for g in groups[s == "test"]])
    correct = probe_correct["naive"][0]
    pivot = summary.pivot(index="model", columns="split", values="accuracy_mean")
    inflation = {m: float(pivot.loc[m, "naive"] - pivot.loc[m, "group_aware"]) for m in pivot.index}
    head = summary[summary.model == "Frozen CNN features + linear head"].set_index("split")
    exposure = read_json(paths.RESULTS / "data_audit" / "naive_split_exposure.json")
    write_json(
        paths.RESULTS / "leakage" / "leakage_summary.json",
        {
            "model": "Frozen ImageNet MobileNetV3-Large features + linear head (3 seeds)",
            "naive": {
                "accuracy": float(head.loc["naive", "accuracy_mean"]),
                "macro_f1": float(head.loc["naive", "macro_f1_mean"]),
                "accuracy_std": float(head.loc["naive", "accuracy_std"]),
            },
            "group_aware": {
                "accuracy": float(head.loc["group_aware", "accuracy_mean"]),
                "macro_f1": float(head.loc["group_aware", "macro_f1_mean"]),
                "accuracy_std": float(head.loc["group_aware", "accuracy_std"]),
            },
            "inflation_accuracy_points": float(
                head.loc["naive", "accuracy_mean"] - head.loc["group_aware", "accuracy_mean"]
            )
            * 100,
            "inflation_ci_seed0": bootstrap_diff(probe_correct["naive"][0], probe_correct["group_aware"][0]),
            "naive_exposed_fraction": exposure["exposed_fraction"],
            "naive_test_accuracy_exposed": float(correct[exposed].mean()),
            "naive_test_accuracy_not_exposed": float(correct[~exposed].mean()),
            "inflation_by_model_points": {m: v * 100 for m, v in inflation.items()},
            "baselines_file": "results/baselines/baselines.json",
        },
    )
    print(summary.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
