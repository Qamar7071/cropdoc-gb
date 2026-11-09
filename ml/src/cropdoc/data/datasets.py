"""PyTorch datasets: manifest rows (PlantVillage) and class folders (PlantDoc, GB field photos)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pandas as pd
import torch
from PIL import Image
from torch.utils.data import Dataset

from cropdoc.data.manifest import absolute

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}


def load_rgb(path: Path) -> Image.Image:
    """Open an image as RGB (closing the file handle)."""
    with Image.open(path) as image:
        return image.convert("RGB")


class ManifestDataset(Dataset):
    """Rows of a manifest/split frame with columns ``path`` and ``label``."""

    def __init__(self, frame: pd.DataFrame, transform: Callable, image_fn: Callable | None = None):
        self.paths = frame["path"].tolist()
        self.labels = frame["label"].astype(int).tolist()
        self.transform = transform
        self.image_fn = image_fn  # optional hook, e.g. background randomization (needs the row index)

    def __len__(self) -> int:
        return len(self.paths)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, int, int]:
        image = load_rgb(absolute(self.paths[index]))
        if self.image_fn is not None:
            image = self.image_fn(image, index)
        return self.transform(image), self.labels[index], index


def folder_frame(root: Path, class_map: dict[str, str] | None = None, class_ids: list[str] | None = None) -> pd.DataFrame:
    """Scan ``root/<folder>/<image>`` into a frame (path, folder, class_id, label).

    ``class_map`` maps folder names to model class ids (e.g. PlantDoc names → PlantVillage ids);
    folders without a mapping get class_id "" (useful for OOD sets).
    """
    rows = []
    if not root.exists():
        return pd.DataFrame(columns=["path", "folder", "class_id", "label"])
    for folder in sorted(p for p in root.iterdir() if p.is_dir()):
        class_id = (class_map or {}).get(folder.name, folder.name if class_map is None else "")
        for image in sorted(folder.rglob("*")):
            if image.suffix.lower() in IMAGE_SUFFIXES and image.is_file():
                label = class_ids.index(class_id) if class_ids and class_id in class_ids else -1
                rows.append({"path": image.as_posix(), "folder": folder.name, "class_id": class_id, "label": label})
    return pd.DataFrame(rows, columns=["path", "folder", "class_id", "label"])
