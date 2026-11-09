"""Image transforms (augmentation policies) built with torchvision.

* eval      Resize(256) → CenterCrop(224) → tensor → ImageNet normalization. The web app copies this
            exactly with Pillow + NumPy (backend/app/services/preprocess.py; parity is tested).
* none      same as eval (the "no augmentation" arm of the experiment matrix)
* standard  random crop/zoom, flips, small rotation, mild colour change
* strong    standard + RandAugment + stronger colour jitter + random erasing
* bgrand    standard + leaf pasted on a random background (see background.py; needs masks)
"""

from __future__ import annotations

from torchvision import transforms as T

MEAN = (0.485, 0.456, 0.406)
STD = (0.229, 0.224, 0.225)
RESIZE, CROP = 256, 224


def _normalize() -> list:
    return [T.ToTensor(), T.Normalize(MEAN, STD)]


def eval_transform(resize: int = RESIZE, crop: int = CROP) -> T.Compose:
    """Deterministic test-time transform."""
    return T.Compose([T.Resize(resize), T.CenterCrop(crop), *_normalize()])


def train_transform(policy: str = "standard", crop: int = CROP) -> T.Compose:
    """Training-time augmentation for the given policy name."""
    if policy in ("none", "eval"):
        return eval_transform(crop=crop)
    standard = [
        T.RandomResizedCrop(crop, scale=(0.5, 1.0), ratio=(0.8, 1.25)),
        T.RandomHorizontalFlip(),
        T.RandomVerticalFlip(),
        T.RandomRotation(15),
        T.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.2, hue=0.02),
    ]
    if policy in ("standard", "bgrand"):
        return T.Compose([*standard, *_normalize()])
    if policy in ("strong", "combined"):
        return T.Compose(
            [
                *standard[:4],
                T.RandAugment(num_ops=2, magnitude=9),
                T.ColorJitter(brightness=0.4, contrast=0.4, saturation=0.4, hue=0.05),
                *_normalize(),
                T.RandomErasing(p=0.25, scale=(0.02, 0.2)),
            ]
        )
    raise ValueError(f"unknown augmentation policy: {policy}")
