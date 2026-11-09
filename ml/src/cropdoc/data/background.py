"""Background randomization: paste the leaf onto a random background during training.

Intuition: in PlantVillage every photo of a class was taken on a similar plain background, so a
model can "cheat" by recognising the background. If, during training, the same leaf appears on many
different backgrounds (soil, grass, noise, other textures), the background stops being useful and the
model is pushed to look at the leaf itself, as it must in a real field.

Leaf masks come from PlantVillage's segmented twins. Backgrounds come from a folder of photos
(``data/backgrounds``, optional) or are generated procedurally (always available, e.g. in tests).
"""

from __future__ import annotations

import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

from cropdoc.data.manifest import absolute

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}


def procedural_background(size: tuple[int, int], rng: random.Random) -> Image.Image:
    """Smooth random texture: low-resolution noise upsampled + a random earthy/green tint + grain."""
    w, h = size
    cells = rng.choice([4, 8, 16, 32])
    np_rng = np.random.default_rng(rng.randrange(1 << 30))
    base = np_rng.random((cells, cells, 3))
    tint = np.array(rng.choice([(0.45, 0.35, 0.2), (0.3, 0.45, 0.2), (0.5, 0.5, 0.45), (0.25, 0.3, 0.35), (0.6, 0.55, 0.4)]))
    texture = Image.fromarray((np.clip(base * 0.6 + tint * 0.6, 0, 1) * 255).astype(np.uint8)).resize(size, Image.Resampling.BICUBIC)
    grain = np_rng.normal(0, rng.uniform(4, 18), (h, w, 3))
    return Image.fromarray(np.clip(np.asarray(texture, dtype=np.float32) + grain, 0, 255).astype(np.uint8))


class BackgroundRandomizer:
    """Callable(image, index) → image with the leaf composited onto a random background.

    ``seg_paths[index]`` is the segmented twin of the photo at ``index`` ("" = no mask → unchanged).
    """

    def __init__(self, seg_paths: list[str], background_dir: Path | None = None, p: float = 0.8, seed: int = 0):
        self.seg_paths = seg_paths
        self.p = p
        self.rng = random.Random(seed)
        self.backgrounds = sorted(
            q for q in (background_dir.rglob("*") if background_dir and background_dir.exists() else [])
            if q.suffix.lower() in IMAGE_SUFFIXES
        )

    def _background(self, size: tuple[int, int]) -> Image.Image:
        if self.backgrounds and self.rng.random() < 0.7:
            with Image.open(self.rng.choice(self.backgrounds)) as image:
                bg = image.convert("RGB")
            scale = max(size[0] / bg.width, size[1] / bg.height) * self.rng.uniform(1.0, 1.6)
            bg = bg.resize((int(bg.width * scale) + 1, int(bg.height * scale) + 1))
            left = self.rng.randint(0, bg.width - size[0])
            top = self.rng.randint(0, bg.height - size[1])
            return bg.crop((left, top, left + size[0], top + size[1]))
        return procedural_background(size, self.rng)

    def __call__(self, image: Image.Image, index: int) -> Image.Image:
        seg = self.seg_paths[index] if index < len(self.seg_paths) else ""
        if not seg or self.rng.random() > self.p:
            return image
        with Image.open(absolute(seg)) as seg_image:
            mask = seg_image.convert("L").resize(image.size).point(lambda v: 255 if v > 18 else 0)
        mask = mask.filter(ImageFilter.MedianFilter(5)).filter(ImageFilter.GaussianBlur(1.5))  # soft edges
        scale = self.rng.uniform(0.7, 1.0)
        leaf_size = (max(1, int(image.width * scale)), max(1, int(image.height * scale)))
        leaf, mask = image.resize(leaf_size), mask.resize(leaf_size)
        canvas = self._background(image.size)
        offset = (self.rng.randint(0, image.width - leaf_size[0]), self.rng.randint(0, image.height - leaf_size[1]))
        canvas.paste(leaf, offset, mask)
        return canvas
