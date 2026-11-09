"""Few-shot adaptation: how many real-world photos per class close the lab→field gap? (``make fewshot``)

Model: frozen ImageNet MobileNetV3-Large features + a linear head (the quick model's first stage),
so each run takes seconds on CPU. For k ∈ {0, 5, 10, 20} and 3 seeds:
  1. sample k photos per class from the real-world POOL (PlantDoc train split), excluding pool photos
     that are near-duplicates of any evaluation photo (no leakage);
  2. train the head on all lab photos + the k-shot photos (up-weighted to ~20% of the data);
  3. evaluate on the fixed real-world EVALUATION set (PlantDoc test split).
k = 0 is the lab-only head. GB field photos get the same treatment once collected (PENDING before).
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import torch  # noqa: E402
from sklearn.model_selection import GroupShuffleSplit  # noqa: E402

from cropdoc import paths  # noqa: E402
from cropdoc.data.classes import CLASS_IDS  # noqa: E402
from cropdoc.embeddings import compute_embeddings, l2_normalize  # noqa: E402
from cropdoc.research.common import (  # noqa: E402
    crop_hint_predictions,
    field_frame,
    load_split,
    log,
    metrics_on_present_classes,
    plantdoc_frame,
)
from cropdoc.utils import seed_everything, write_json  # noqa: E402

KS = [0, 5, 10, 20]
SEEDS = [0, 1, 2]
ARCH = "mobilenetv3_large_100"
NEAR_DUPLICATE_COSINE = 0.95


def train_head(
    x: np.ndarray, y: np.ndarray, weights: np.ndarray, seed: int, epochs: int = 12
) -> torch.nn.Linear:
    """Weighted multinomial logistic regression (linear layer) with AdamW."""
    seed_everything(seed)
    layer = torch.nn.Linear(x.shape[1], len(CLASS_IDS))
    optimizer = torch.optim.AdamW(layer.parameters(), lr=2e-3, weight_decay=1e-4)
    xt, yt, wt = torch.from_numpy(x), torch.from_numpy(y).long(), torch.from_numpy(weights).float()
    generator = torch.Generator().manual_seed(seed)
    for _ in range(epochs):
        for idx in torch.randperm(len(xt), generator=generator).split(512):
            loss = (
                torch.nn.functional.cross_entropy(layer(xt[idx]), yt[idx], reduction="none") * wt[idx]
            ).sum() / wt[idx].sum()
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
    return layer.eval()


def sample_k(pool: pd.DataFrame, k: int, seed: int) -> pd.DataFrame:
    """k random photos per class (all of them for classes with fewer than k)."""
    if k == 0:
        return pool.iloc[:0]
    return pd.concat([g.sample(min(k, len(g)), random_state=seed) for _, g in pool.groupby("label")])


def run_curve(lab_x, lab_y, pool: pd.DataFrame, pool_x, evaluation: pd.DataFrame, eval_x) -> dict:
    y_eval = evaluation.label.to_numpy()
    rows = []
    for k in KS:
        for seed in SEEDS:
            support = sample_k(pool.assign(_i=np.arange(len(pool))), k, seed)
            x = lab_x if k == 0 else np.concatenate([lab_x, pool_x[support._i.to_numpy()]])
            y = lab_y if k == 0 else np.concatenate([lab_y, support.label.to_numpy()])
            weights = np.ones(len(y), dtype=np.float32)
            if k:  # field photos get ~20% of the total weight
                weights[len(lab_y) :] = 0.25 * len(lab_y) / max(1, len(support))
            head = train_head(x, y, weights, seed)
            with torch.no_grad():
                logits = head(torch.from_numpy(eval_x)).numpy()
            metrics = metrics_on_present_classes(y_eval, logits.argmax(1))
            hint = metrics_on_present_classes(y_eval, crop_hint_predictions(logits, y_eval))
            rows.append(
                {
                    "k": k,
                    "seed": seed,
                    "support_photos": int(len(support)),
                    "accuracy": metrics["accuracy"],
                    "macro_f1": metrics["macro_f1"],
                    "crop_hint_accuracy": hint["accuracy"],
                }
            )
            log.info(
                "k=%d seed=%d acc=%.3f f1=%.3f hint=%.3f",
                k,
                seed,
                metrics["accuracy"],
                metrics["macro_f1"],
                hint["accuracy"],
            )
    frame = pd.DataFrame(rows)
    agg = frame.groupby("k").agg(["mean", "std"])
    return {
        "k": KS,
        "seeds": SEEDS,
        "accuracy_mean": agg[("accuracy", "mean")].tolist(),
        "accuracy_std": agg[("accuracy", "std")].fillna(0).tolist(),
        "macro_f1_mean": agg[("macro_f1", "mean")].tolist(),
        "macro_f1_std": agg[("macro_f1", "std")].fillna(0).tolist(),
        "crop_hint_accuracy_mean": agg[("crop_hint_accuracy", "mean")].tolist(),
        "crop_hint_accuracy_std": agg[("crop_hint_accuracy", "std")].fillna(0).tolist(),
        "runs": rows,
        "n_eval": int(len(evaluation)),
        "n_eval_classes": int(evaluation.label.nunique()),
    }


def drop_near_duplicates(
    pool: pd.DataFrame, pool_x: np.ndarray, eval_x: np.ndarray
) -> tuple[pd.DataFrame, np.ndarray, int]:
    """Remove pool photos whose embedding is almost identical to any evaluation photo."""
    sims = l2_normalize(pool_x) @ l2_normalize(eval_x).T
    keep = sims.max(axis=1) < NEAR_DUPLICATE_COSINE
    return pool[keep].reset_index(drop=True), pool_x[keep], int((~keep).sum())


def plot(curve: dict, title: str, path) -> None:
    fig, ax = plt.subplots(figsize=(5.5, 3.8))
    ax.errorbar(
        curve["k"],
        curve["accuracy_mean"],
        yerr=curve["accuracy_std"],
        marker="o",
        capsize=4,
        label="accuracy",
    )
    ax.errorbar(
        curve["k"],
        curve["crop_hint_accuracy_mean"],
        yerr=curve["crop_hint_accuracy_std"],
        marker="s",
        capsize=4,
        label="accuracy with crop hint",
    )
    ax.plot(curve["k"], curve["macro_f1_mean"], marker="^", label="macro-F1")
    ax.set(
        xlabel="real-world photos per class used for adaptation (k)",
        ylabel="score on held-out real-world photos",
        title=title,
        ylim=(0, 1),
    )
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=150)


def main() -> int:
    split = load_split("group_aware")
    pv_x = compute_embeddings(split[["path"]], ARCH)
    train_rows = split.split.to_numpy() == "train"
    lab_x, lab_y = pv_x[train_rows], split.label.to_numpy()[train_rows]

    plantdoc = plantdoc_frame()
    pd_x = compute_embeddings(plantdoc[["path"]], ARCH)
    is_pool = plantdoc.split.to_numpy() == "train"
    pool, pool_x = plantdoc[is_pool].reset_index(drop=True), pd_x[is_pool]
    evaluation, eval_x = plantdoc[~is_pool].reset_index(drop=True), pd_x[~is_pool]
    pool, pool_x, removed = drop_near_duplicates(pool, pool_x, eval_x)
    curve = run_curve(lab_x, lab_y, pool, pool_x, evaluation, eval_x)
    curve.update(
        {
            "dataset": "PlantDoc (public real-world web photos; pool = PlantDoc train, evaluation = PlantDoc test)",
            "model": "frozen ImageNet MobileNetV3-Large features + linear head (lab-trained, then adapted)",
            "pool_photos": int(len(pool)),
            "pool_near_duplicates_removed": removed,
            "figure": "results/shift/fewshot_plantdoc.png",
        }
    )
    (paths.RESULTS / "shift").mkdir(parents=True, exist_ok=True)
    plot(curve, "Few-shot adaptation (PlantDoc)", paths.RESULTS / "shift" / "fewshot_plantdoc.png")
    write_json(paths.RESULTS / "shift" / "fewshot_plantdoc.json", curve)

    field = field_frame()
    if field.empty or field.label.nunique() < 2:
        log.warning("PENDING: GB few-shot needs field photos in %s", paths.FIELD_TEST)
        return 0
    field_x = compute_embeddings(field[["path"]], ARCH)
    splitter = GroupShuffleSplit(
        n_splits=1, test_size=0.5, random_state=0
    )  # same leaf never in pool and test
    pool_idx, eval_idx = next(splitter.split(field, field.label, field.photo_group))
    gb_pool, gb_eval = (
        field.iloc[pool_idx].reset_index(drop=True),
        field.iloc[eval_idx].reset_index(drop=True),
    )
    gb = run_curve(lab_x, lab_y, gb_pool, field_x[pool_idx], gb_eval, field_x[eval_idx])
    gb.update(
        {
            "dataset": "Gilgit-Baltistan field photos (pool/evaluation split by plant+leaf id)",
            "model": curve["model"],
            "figure": "results/shift/fewshot_field.png",
        }
    )
    plot(gb, "Few-shot adaptation (GB field photos)", paths.RESULTS / "shift" / "fewshot_field.png")
    write_json(paths.RESULTS / "shift" / "fewshot_field.json", gb)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
