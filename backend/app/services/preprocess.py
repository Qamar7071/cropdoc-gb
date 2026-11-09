"""Image preprocessing that exactly matches the training-time evaluation transform.

Training (torchvision) uses: Resize(256) → CenterCrop(224) → ToTensor → Normalize(ImageNet).
We re-implement the same steps with Pillow + NumPy so the app does not need PyTorch.
``ml/tests/test_export.py`` checks that both versions give identical arrays.
"""

from __future__ import annotations

import numpy as np
from PIL import Image

RESIZE = 256
CROP = 224
MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


def resize_shorter_side(image: Image.Image, size: int = RESIZE) -> Image.Image:
    """Resize so the shorter side equals ``size`` (same rounding as torchvision.transforms.Resize)."""
    width, height = image.size
    if width <= height:
        new_w, new_h = size, int(size * height / width)
    else:
        new_w, new_h = int(size * width / height), size
    if (new_w, new_h) == (width, height):
        return image
    return image.resize((new_w, new_h), Image.Resampling.BILINEAR)


def center_crop(image: Image.Image, size: int = CROP) -> Image.Image:
    """Center crop to ``size``×``size`` (same rounding as torchvision.transforms.CenterCrop)."""
    width, height = image.size
    top = int(round((height - size) / 2.0))
    left = int(round((width - size) / 2.0))
    return image.crop((left, top, left + size, top + size))


def model_input_image(image: Image.Image, resize: int = RESIZE, crop: int = CROP) -> Image.Image:
    """The RGB crop the model actually sees (also used as the Grad-CAM background)."""
    return center_crop(resize_shorter_side(image.convert("RGB"), resize), crop)


def to_tensor(image: Image.Image, mean: np.ndarray = MEAN, std: np.ndarray = STD) -> np.ndarray:
    """HWC uint8 image → normalized NCHW float32 array with a batch dimension of 1."""
    array = np.asarray(image, dtype=np.float32) / 255.0
    array = (array - mean) / std
    return array.transpose(2, 0, 1)[None].astype(np.float32)


def preprocess(image: Image.Image, resize: int = RESIZE, crop: int = CROP) -> tuple[np.ndarray, Image.Image]:
    """Return (model input array, the cropped RGB image) for one photo."""
    cropped = model_input_image(image, resize, crop)
    return to_tensor(cropped), cropped
