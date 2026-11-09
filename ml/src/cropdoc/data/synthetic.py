"""A tiny synthetic "leaf" dataset for smoke tests and CI (no downloads, seconds on CPU).

Each class is a coloured ellipse with class-specific spots on a plain background, plus a matching
"segmented" twin (ellipse on black) so background randomization can be tested too.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw


def make_synthetic_dataset(root: Path, n_classes: int = 3, per_class: int = 24, size: int = 64, seed: int = 0) -> pd.DataFrame:
    """Write images to ``root`` and return a split frame (path, class_id, label, group, split, seg_path)."""
    rng = np.random.default_rng(seed)
    rows = []
    for label in range(n_classes):
        colour = tuple(int(c) for c in rng.integers(40, 220, 3))
        for i in range(per_class):
            image = Image.new("RGB", (size, size), (200, 200, 200))
            seg = Image.new("RGB", (size, size), (0, 0, 0))
            box = [int(size * 0.15), int(size * 0.2), int(size * 0.85), int(size * 0.8)]
            for canvas in (image, seg):
                draw = ImageDraw.Draw(canvas)
                draw.ellipse(box, fill=colour)
                for _ in range(label + 1):  # class-specific number of spots
                    x, y = rng.integers(box[0] + 6, box[2] - 6), rng.integers(box[1] + 6, box[3] - 6)
                    draw.ellipse([x - 3, y - 3, x + 3, y + 3], fill=(60, 40, 20))
            path = root / f"class{label}" / f"img{i:03d}.png"
            seg_path = root / "segmented" / f"class{label}" / f"img{i:03d}.png"
            path.parent.mkdir(parents=True, exist_ok=True)
            seg_path.parent.mkdir(parents=True, exist_ok=True)
            image.save(path)
            seg.save(seg_path)
            split = "train" if i < per_class * 0.6 else "val" if i < per_class * 0.8 else "test"
            rows.append({"path": str(path), "class_id": f"class{label}", "label": label, "group": f"{label}-{i // 2}",
                         "split": split, "seg_path": str(seg_path)})
    return pd.DataFrame(rows)
