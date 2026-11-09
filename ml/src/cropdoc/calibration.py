"""Calibration: does "90% confident" really mean right 90% of the time?

* **ECE (expected calibration error):** sort predictions into confidence bins (0-10%, ..., 90-100%);
  in each bin compare average confidence with actual accuracy; ECE is the weighted average gap.
  0 = perfectly calibrated.
* **Temperature scaling:** divide all logits by one number T (fitted on validation data) before the
  softmax. T > 1 softens over-confident predictions. It never changes which class wins, so
  accuracy is unchanged; only the confidence becomes more honest.
"""

from __future__ import annotations

import numpy as np


def softmax(logits: np.ndarray) -> np.ndarray:
    """Row-wise stable softmax."""
    shifted = logits - logits.max(axis=1, keepdims=True)
    exp = np.exp(shifted)
    return exp / exp.sum(axis=1, keepdims=True)


def reliability_bins(probs: np.ndarray, labels: np.ndarray, n_bins: int = 15) -> list[dict]:
    """Per-bin confidence, accuracy and count (equal-width bins over the top-class confidence)."""
    confidence = probs.max(axis=1)
    correct = probs.argmax(axis=1) == labels
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    rows = []
    for lo, hi in zip(edges[:-1], edges[1:], strict=True):
        in_bin = (confidence > lo) & (confidence <= hi) if lo > 0 else (confidence >= lo) & (confidence <= hi)
        count = int(in_bin.sum())
        rows.append(
            {
                "lo": float(lo),
                "hi": float(hi),
                "count": count,
                "confidence": float(confidence[in_bin].mean()) if count else None,
                "accuracy": float(correct[in_bin].mean()) if count else None,
            }
        )
    return rows


def expected_calibration_error(probs: np.ndarray, labels: np.ndarray, n_bins: int = 15) -> float:
    """ECE = Σ_bins (n_bin / N) · |accuracy_bin − confidence_bin|."""
    total = len(labels)
    return float(
        sum(
            b["count"] / total * abs(b["accuracy"] - b["confidence"])
            for b in reliability_bins(probs, labels, n_bins)
            if b["count"]
        )
    )


def negative_log_likelihood(logits: np.ndarray, labels: np.ndarray, temperature: float = 1.0) -> float:
    """Average −log p(true class) after dividing logits by the temperature."""
    scaled = logits / temperature
    shifted = scaled - scaled.max(axis=1, keepdims=True)
    log_probs = shifted - np.log(np.exp(shifted).sum(axis=1, keepdims=True))
    return float(-log_probs[np.arange(len(labels)), labels].mean())


def fit_temperature(logits: np.ndarray, labels: np.ndarray, lo: float = 0.05, hi: float = 20.0) -> float:
    """Temperature minimizing validation NLL (golden-section search on log T; NLL is unimodal in T)."""
    a, b = np.log(lo), np.log(hi)
    ratio = (np.sqrt(5) - 1) / 2
    c, d = b - ratio * (b - a), a + ratio * (b - a)
    for _ in range(80):
        if negative_log_likelihood(logits, labels, np.exp(c)) < negative_log_likelihood(
            logits, labels, np.exp(d)
        ):
            b = d
        else:
            a = c
        c, d = b - ratio * (b - a), a + ratio * (b - a)
    return float(np.exp((a + b) / 2))


def selective_curve(
    confidence: np.ndarray, correct: np.ndarray, thresholds: np.ndarray | None = None
) -> list[dict]:
    """Coverage (share of predictions kept) and accuracy on the kept ones, for each threshold."""
    thresholds = np.linspace(0.0, 0.99, 100) if thresholds is None else thresholds
    rows = []
    for t in thresholds:
        keep = confidence >= t
        rows.append(
            {
                "threshold": float(t),
                "coverage": float(keep.mean()),
                "accuracy": float(correct[keep].mean()) if keep.any() else None,
            }
        )
    return rows


def threshold_for_accuracy(
    confidence: np.ndarray, correct: np.ndarray, target_accuracy: float, floor: float = 0.5
) -> dict:
    """Smallest confidence threshold (≥ floor) whose kept predictions reach ``target_accuracy``."""
    for row in selective_curve(confidence, correct, np.round(np.arange(floor, 0.995, 0.005), 3)):
        if row["accuracy"] is not None and row["accuracy"] >= target_accuracy:
            return {**row, "target_accuracy": target_accuracy, "reached": True}
    last = selective_curve(confidence, correct, np.array([0.99]))[0]
    return {**last, "target_accuracy": target_accuracy, "reached": False}
