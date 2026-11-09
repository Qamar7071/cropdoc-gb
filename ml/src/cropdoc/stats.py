"""Bootstrap confidence intervals.

Intuition: we only have one test set, so we "re-run" the test many times by resampling its
photos with replacement and recomputing the metric. The spread of those values tells us how
much the number could move by chance. A 95% interval that excludes 0 for a *difference*
means the difference is unlikely to be luck.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np


def bootstrap_ci(
    values: np.ndarray,
    statistic: Callable[[np.ndarray], float] = np.mean,
    n: int = 2000,
    seed: int = 0,
    level: float = 0.95,
) -> dict:
    """Percentile bootstrap CI of ``statistic`` over one sample (e.g. per-photo correctness)."""
    rng = np.random.default_rng(seed)
    values = np.asarray(values)
    stats = np.array([statistic(values[rng.integers(0, len(values), len(values))]) for _ in range(n)])
    lo, hi = np.quantile(stats, [(1 - level) / 2, 1 - (1 - level) / 2])
    return {
        "estimate": float(statistic(values)),
        "ci_low": float(lo),
        "ci_high": float(hi),
        "level": level,
        "n_boot": n,
    }


def bootstrap_diff(
    a: np.ndarray,
    b: np.ndarray,
    statistic: Callable[[np.ndarray], float] = np.mean,
    n: int = 2000,
    seed: int = 0,
    level: float = 0.95,
    paired: bool = False,
) -> dict:
    """CI of statistic(a) − statistic(b). Paired: same photos in both (resample indices jointly)."""
    rng = np.random.default_rng(seed)
    a, b = np.asarray(a), np.asarray(b)
    diffs = np.empty(n)
    for i in range(n):
        if paired:
            idx = rng.integers(0, len(a), len(a))
            diffs[i] = statistic(a[idx]) - statistic(b[idx])
        else:
            diffs[i] = statistic(a[rng.integers(0, len(a), len(a))]) - statistic(
                b[rng.integers(0, len(b), len(b))]
            )
    lo, hi = np.quantile(diffs, [(1 - level) / 2, 1 - (1 - level) / 2])
    return {
        "estimate": float(statistic(a) - statistic(b)),
        "ci_low": float(lo),
        "ci_high": float(hi),
        "level": level,
        "n_boot": n,
        "paired": paired,
    }


def auroc(scores_in: np.ndarray, scores_out: np.ndarray) -> float:
    """Area under the ROC curve for 'higher score = more likely out-of-distribution'.

    Equals the probability that a random OOD photo scores higher than a random in-distribution one.
    """
    scores = np.concatenate([scores_in, scores_out])
    order = scores.argsort()
    ranks = np.empty(len(scores))
    ranks[order] = np.arange(1, len(scores) + 1)
    # average ranks for ties
    _, inverse, counts = np.unique(scores, return_inverse=True, return_counts=True)
    sums = np.bincount(inverse, weights=ranks)
    ranks = (sums / counts)[inverse]
    rank_out = ranks[len(scores_in) :].sum()
    n_in, n_out = len(scores_in), len(scores_out)
    return float((rank_out - n_out * (n_out + 1) / 2) / (n_in * n_out))


def fpr_at_tpr(scores_in: np.ndarray, scores_out: np.ndarray, tpr: float = 0.95) -> float:
    """Share of OOD photos *accepted* when the threshold keeps ``tpr`` of in-distribution photos."""
    threshold = np.quantile(scores_in, tpr)
    return float((scores_out <= threshold).mean())
