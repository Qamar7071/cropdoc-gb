"""Make a large, phone-camera-sized JPEG (well over 3.5 MB) from a leaf photo, for the upload test.

Usage: python make_big_photo.py <photo.jpg> <out.jpg>
"""

import sys

import numpy as np
from PIL import Image

leaf = Image.open(sys.argv[1]).convert("RGB").resize((4000, 3000), Image.Resampling.BICUBIC)
pixels = np.asarray(leaf, dtype=np.int16)
noise = np.random.default_rng(0).integers(-12, 13, size=pixels.shape)  # sensor-like grain: hard to compress
Image.fromarray(np.clip(pixels + noise, 0, 255).astype(np.uint8)).save(sys.argv[2], "JPEG", quality=97)
