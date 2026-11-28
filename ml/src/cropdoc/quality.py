"""Photo quality measurement for calibration (identical to backend/app/services/quality.py::measure).

Training code must not import backend code, so the small function is duplicated here; a test in
ml/tests checks that both give the same numbers.
"""

from __future__ import annotations

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
