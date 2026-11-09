"""Uncertainty scores and the decision between confident / low confidence / unsupported.

Intuition
---------
* **Max-softmax probability (MSP):** how sure the model is about its top answer. Low MSP means
  "I can't decide between diseases", so we say "not sure, consult an expert".
* **Energy score:** computed from *all* raw scores (logits). Photos unlike anything seen in
  training (a hand, a wall, an apricot leaf) tend to give small logits for every class, so the
  energy is high. High energy means "this does not look like a supported leaf".
Both thresholds are chosen on validation data (see ``calibration.json``).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

CONFIDENT = "confident"
LOW_CONFIDENCE = "low_confidence"
UNSUPPORTED = "not_a_leaf_or_unsupported_crop"


def softmax(logits: np.ndarray, axis: int = -1) -> np.ndarray:
    """Numerically stable softmax (works with -inf entries for masked classes)."""
    shifted = logits - np.max(logits, axis=axis, keepdims=True)
    exp = np.exp(shifted)
    return exp / np.sum(exp, axis=axis, keepdims=True)


def logsumexp(values: np.ndarray, axis: int = -1) -> np.ndarray:
    """Stable log(sum(exp(values)))."""
    peak = np.max(values, axis=axis, keepdims=True)
    return (peak + np.log(np.sum(np.exp(values - peak), axis=axis, keepdims=True))).squeeze(axis)


def energy_score(logits: np.ndarray, temperature: float = 1.0) -> np.ndarray:
    """Energy E(x) = -T·logsumexp(logits/T). Higher energy → more likely out-of-distribution."""
    return -temperature * logsumexp(logits / temperature, axis=-1)


@dataclass(frozen=True)
class Thresholds:
    """Decision thresholds; ``provisional`` is shown in the API until OOD evaluation is done."""

    min_confidence: float = 0.5
    max_energy: float | None = None
    provisional: bool = True
    source: str = "placeholder (not yet calibrated)"

    @classmethod
    def from_dict(cls, data: dict | None) -> Thresholds:
        """Build from the ``thresholds`` block of calibration.json (missing → placeholder)."""
        if not data:
            return cls()
        return cls(
            min_confidence=float(data.get("min_confidence", 0.5)),
            max_energy=None if data.get("max_energy") is None else float(data["max_energy"]),
            provisional=bool(data.get("provisional", True)),
            source=str(data.get("source", "calibration.json")),
        )


def decide_status(confidence: float, energy: float, thresholds: Thresholds) -> str:
    """Map scores to a status. Unsupported is checked first (it is the stronger warning)."""
    if thresholds.max_energy is not None and energy > thresholds.max_energy:
        return UNSUPPORTED
    if confidence < thresholds.min_confidence:
        return LOW_CONFIDENCE
    return CONFIDENT
