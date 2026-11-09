"""Leaf masks from PlantVillage's background-removed ("segmented") twins.

The segmented copy shows the leaf on a black background, aligned pixel-for-pixel with the colour
photo, so "pixel is not black" ≈ "pixel is leaf". A small morphological clean-up removes speckles.
"""

from __future__ import annotations

import numpy as np
from PIL import Image, ImageFilter

from cropdoc.data.manifest import absolute

RESIZE, CROP = 256, 224


def leaf_mask(seg_path: str, size: tuple[int, int] | None = None, threshold: int = 18) -> np.ndarray:
    """Boolean leaf mask (True = leaf) at the photo's resolution (or ``size``)."""
    with Image.open(absolute(seg_path)) as image:
        gray = image.convert("L")
        if size and gray.size != size:
            gray = gray.resize(size, Image.Resampling.NEAREST)
    binary = gray.point(lambda v: 255 if v > threshold else 0)
    cleaned = binary.filter(ImageFilter.MedianFilter(5))
    return np.asarray(cleaned) > 127


def model_view_mask(mask: np.ndarray) -> np.ndarray:
    """Apply the eval transform's resize(256) + centre-crop(224) to a mask."""
    image = Image.fromarray(mask.astype(np.uint8) * 255)
    w, h = image.size
    new = (RESIZE, int(RESIZE * h / w)) if w <= h else (int(RESIZE * w / h), RESIZE)
    image = image.resize(new, Image.Resampling.NEAREST)
    left, top = int(round((new[0] - CROP) / 2.0)), int(round((new[1] - CROP) / 2.0))
    return np.asarray(image.crop((left, top, left + CROP, top + CROP))) > 127
