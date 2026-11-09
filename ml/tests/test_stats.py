"""Statistics helpers on inputs with known answers."""

from __future__ import annotations

import numpy as np

from cropdoc.stats import auroc, bootstrap_ci, bootstrap_diff, fpr_at_tpr


def test_auroc_known_values():
    assert auroc(np.array([0.0, 1.0]), np.array([2.0, 3.0])) == 1.0  # perfect separation
    assert auroc(np.array([2.0, 3.0]), np.array([0.0, 1.0])) == 0.0
    assert auroc(np.array([1.0, 1.0]), np.array([1.0, 1.0])) == 0.5  # ties = coin flip


def test_fpr_at_tpr():
    scores_in = np.arange(100, dtype=float)  # threshold at the 95th percentile ≈ 94.05
    assert fpr_at_tpr(scores_in, np.array([10.0, 99.0, 200.0])) == 1 / 3


def test_bootstrap_intervals_contain_the_estimate():
    rng = np.random.default_rng(0)
    values = rng.random(500) < 0.7
    ci = bootstrap_ci(values.astype(float), n=500)
    assert ci["ci_low"] <= ci["estimate"] <= ci["ci_high"] and abs(ci["estimate"] - values.mean()) < 1e-12
    diff = bootstrap_diff(np.ones(200), np.zeros(200), n=200)
    assert diff["estimate"] == 1.0 and diff["ci_low"] == 1.0
    paired = bootstrap_diff(values.astype(float), values.astype(float), n=200, paired=True)
    assert paired["ci_low"] == paired["ci_high"] == 0.0
