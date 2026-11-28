"""Is this photo good enough to analyse? Brightness and sharpness checks before trusting the model.

Intuition:
  * brightness = average grey level (0 = black, 255 = white). Very dark or washed-out photos hide the
    colours and spots the model looks for.
  * sharpness = how much the grey level changes between neighbouring pixels ("variance of the
    Laplacian"). A blurry photo has soft edges, so this number is small.

The limits are NOT guessed: ``python -m cropdoc.research.quality`` measures them on validation photos
(lab and field) and writes ``models/active/quality.json``. Without that file the check is skipped and
the response says ``checked: false``. The same measurement code exists in ml/src/cropdoc/quality.py
(a test keeps both identical).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

MEASURE_SIDE = 384  # measure on a fixed size so phone photos and small web photos are comparable


def measure(image: Image.Image) -> dict[str, float]:
    """Brightness (mean grey 0-255) and sharpness (variance of the 4-neighbour Laplacian)."""
    gray = image.convert("L")
    scale = MEASURE_SIDE / max(gray.size)
    if scale < 1:
        gray = gray.resize(
            (max(1, round(gray.width * scale)), max(1, round(gray.height * scale))), Image.Resampling.BILINEAR
        )
    a = np.asarray(gray, dtype=np.float32)
    if a.shape[0] < 3 or a.shape[1] < 3:
        return {"brightness": float(a.mean()), "sharpness": 0.0}
    lap = a[1:-1, 2:] + a[1:-1, :-2] + a[2:, 1:-1] + a[:-2, 1:-1] - 4 * a[1:-1, 1:-1]
    return {"brightness": float(a.mean()), "sharpness": float(lap.var())}


@dataclass
class QualityThresholds:
    """Limits from models/active/quality.json (None = check disabled)."""

    min_brightness: float | None = None
    max_brightness: float | None = None
    min_sharpness: float | None = None
    source: str = ""

    @classmethod
    def load(cls, path: Path) -> QualityThresholds:
        if not path.exists():
            return cls()
        data = json.loads(path.read_text(encoding="utf-8"))
        limits = data.get("thresholds", {})
        return cls(
            min_brightness=limits.get("min_brightness"),
            max_brightness=limits.get("max_brightness"),
            min_sharpness=limits.get("min_sharpness"),
            source=data.get("source", ""),
        )

    @property
    def enabled(self) -> bool:
        return any(v is not None for v in (self.min_brightness, self.max_brightness, self.min_sharpness))

    def assess(self, image: Image.Image) -> dict:
        """{'checked', 'ok', 'issues', 'brightness', 'sharpness'} for the API response."""
        if not self.enabled:
            return {"checked": False, "ok": True, "issues": []}
        m = measure(image)
        issues = []
        if self.min_brightness is not None and m["brightness"] < self.min_brightness:
            issues.append("too_dark")
        if self.max_brightness is not None and m["brightness"] > self.max_brightness:
            issues.append("too_bright")
        if self.min_sharpness is not None and m["sharpness"] < self.min_sharpness:
            issues.append("blurry")
        return {"checked": True, "ok": not issues, "issues": issues, **{k: round(v, 2) for k, v in m.items()}}
