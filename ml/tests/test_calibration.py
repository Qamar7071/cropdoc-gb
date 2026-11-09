"""Calibration functions on inputs with known answers."""

from __future__ import annotations

import numpy as np

from cropdoc.calibration import (
    expected_calibration_error,
    fit_temperature,
    negative_log_likelihood,
    reliability_bins,
    softmax,
    threshold_for_accuracy,
)


def test_ece_is_zero_when_confidence_matches_accuracy():
    # 10 predictions at confidence 0.8, 8 of them correct → perfectly calibrated
    probs = np.tile([0.8, 0.2], (10, 1))
    labels = np.array([0] * 8 + [1] * 2)
    assert expected_calibration_error(probs, labels) < 1e-12


def test_ece_known_value_for_overconfidence():
    # confidence 0.9 but only 50% correct → ECE = 0.4
    probs = np.tile([0.9, 0.1], (10, 1))
    labels = np.array([0] * 5 + [1] * 5)
    assert abs(expected_calibration_error(probs, labels) - 0.4) < 1e-12


def test_reliability_bins_count_everything():
    rng = np.random.default_rng(0)
    probs = softmax(rng.normal(size=(200, 4)))
    labels = rng.integers(0, 4, 200)
    assert sum(b["count"] for b in reliability_bins(probs, labels)) == 200


def test_temperature_recovers_known_scaling():
    """Logits generated as (true_logits × 3) are over-confident by T=3; fitting should find ≈3."""
    rng = np.random.default_rng(1)
    true_logits = rng.normal(size=(20000, 5)) * 1.5
    labels = np.array([rng.choice(5, p=p) for p in softmax(true_logits)])
    temperature = fit_temperature(true_logits * 3.0, labels)
    assert abs(temperature - 3.0) < 0.15
    assert negative_log_likelihood(true_logits * 3.0, labels, temperature) < negative_log_likelihood(
        true_logits * 3.0, labels, 1.0
    )


def test_threshold_for_accuracy():
    confidence = np.array([0.55, 0.6, 0.7, 0.8, 0.9, 0.95])
    correct = np.array([False, False, True, True, True, True])
    choice = threshold_for_accuracy(confidence, correct, target_accuracy=1.0)
    assert choice["reached"] and 0.6 < choice["threshold"] <= 0.7 and abs(choice["coverage"] - 4 / 6) < 1e-12
