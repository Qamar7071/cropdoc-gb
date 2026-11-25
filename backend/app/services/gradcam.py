"""Turn the model's class activation map (CAM) into a coloured heatmap and an overlay.

Intuition: the model's last convolution layer produces a 7×7 grid of features. For the predicted
class, the CAM weights each grid cell by how much it pushed the score up. Because our model ends
with global-average-pooling + one linear layer, this CAM is *exactly* Grad-CAM (proved by a unit
test in ml/tests). We stretch the 7×7 grid to the image size and colour it: red = most important.
"""

from __future__ import annotations

import base64
import io

import numpy as np
from PIL import Image


def normalize_cam(cam: np.ndarray) -> np.ndarray:
    """ReLU then scale to [0, 1] (an all-zero map stays zero)."""
    cam = np.maximum(cam.astype(np.float32), 0.0)
    peak = float(cam.max())
    return cam / peak if peak > 0 else cam


def colormap(values: np.ndarray) -> np.ndarray:
    """Map values in [0, 1] to RGB uint8 with a blue→cyan→yellow→red ramp (jet-like, no matplotlib)."""
    v = np.clip(values, 0.0, 1.0)
    r = np.clip(1.5 - np.abs(4.0 * v - 3.0), 0.0, 1.0)
    g = np.clip(1.5 - np.abs(4.0 * v - 2.0), 0.0, 1.0)
    b = np.clip(1.5 - np.abs(4.0 * v - 1.0), 0.0, 1.0)
    return (np.stack([r, g, b], axis=-1) * 255).astype(np.uint8)


def heatmap_image(cam: np.ndarray, size: tuple[int, int]) -> Image.Image:
    """Upsample a CAM to ``size`` (bilinear) and colour it."""
    small = Image.fromarray((normalize_cam(cam) * 255).astype(np.uint8), mode="L")
    big = np.asarray(small.resize(size, Image.Resampling.BILINEAR), dtype=np.float32) / 255.0
    return Image.fromarray(colormap(big), mode="RGB")


def heatmap_rgba(cam: np.ndarray, size: tuple[int, int]) -> Image.Image:
    """Coloured heatmap whose transparency follows the CAM (for drawing over a live camera view).

    Weak regions are fully transparent, so the farmer still sees the leaf; strong regions glow.
    """
    small = Image.fromarray((normalize_cam(cam) * 255).astype(np.uint8), mode="L")
    big = np.asarray(small.resize(size, Image.Resampling.BILINEAR), dtype=np.float32) / 255.0
    alpha = (np.clip((big - 0.5) / 0.5, 0.0, 1.0) ** 0.8 * 0.75 * 255).astype(np.uint8)
    return Image.fromarray(np.dstack([colormap(big), alpha]), mode="RGBA")


def overlay(image: Image.Image, heatmap: Image.Image, alpha: float = 0.45) -> Image.Image:
    """Blend the heatmap over the photo."""
    return Image.blend(image.convert("RGB"), heatmap.resize(image.size), alpha)


def png_bytes(image: Image.Image) -> bytes:
    """Encode as optimized PNG."""
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def jpeg_bytes(image: Image.Image, quality: int = 88) -> bytes:
    """Encode as JPEG (no EXIF is ever written)."""
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, format="JPEG", quality=quality, optimize=True)
    return buffer.getvalue()


def b64(data: bytes) -> str:
    """Base64 text for JSON responses."""
    return base64.b64encode(data).decode("ascii")
