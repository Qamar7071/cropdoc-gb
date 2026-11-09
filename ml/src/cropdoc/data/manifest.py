"""Build a manifest (one row per PlantVillage image) with labels and the official leaf map.

Columns
-------
path      image path relative to the data folder (portable between laptop and Colab)
class_id  PlantVillage folder name; label = index in CLASS_IDS
leaf_key  photo id from the file name, e.g. "rs_hl 1864" (used by leaf-map.json)
leaf_id   "<class_id>:::<leaf number>" from leaf-map.json, or "" if the photo is not mapped
seg_path  background-removed twin (gives a leaf mask), "" if missing
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from cropdoc import paths
from cropdoc.data.classes import CLASS_IDS

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}


def leaf_key_from_filename(filename: str) -> str:
    """'00fc...___RS_HL 1864.JPG' → 'rs_hl 1864' (the key used in leaf-map.json)."""
    stem = Path(filename).stem
    return stem.split("___", 1)[1].lower() if "___" in stem else stem.lower()


def load_leaf_map(path: Path) -> dict[str, list[tuple[str, str]]]:
    """leaf-map.json → {leaf_key: [(class_id, leaf_number), ...]} (a key can appear in several classes)."""
    if not path.exists():
        return {}
    raw = json.loads(path.read_text())
    return {key: [tuple(v.split(":::", 1)) for v in values] for key, values in raw.items()}


def build_manifest(color_root: Path | None = None, leaf_map_path: Path | None = None) -> pd.DataFrame:
    """Scan the colour images and attach labels, leaf ids and mask paths."""
    color_root = color_root or paths.PV_COLOR
    seg_root = color_root.parent / "segmented"
    leaf_map = load_leaf_map(leaf_map_path or paths.PV_LEAF_MAP)
    label_of = {c: i for i, c in enumerate(CLASS_IDS)}

    rows = []
    for class_dir in sorted(p for p in color_root.iterdir() if p.is_dir()):
        class_id = class_dir.name
        if class_id not in label_of:
            raise ValueError(f"unexpected class folder: {class_id}")
        for image_path in sorted(class_dir.iterdir()):
            if image_path.suffix.lower() not in IMAGE_SUFFIXES:
                continue
            key = leaf_key_from_filename(image_path.name)
            leaf_number = next((n for c, n in leaf_map.get(key, []) if c == class_id), None)
            seg = seg_root / class_id / f"{image_path.stem}_final_masked.jpg"
            rows.append(
                {
                    "path": _relative(image_path),
                    "class_id": class_id,
                    "label": label_of[class_id],
                    "leaf_key": key,
                    "leaf_id": f"{class_id}:::{leaf_number}" if leaf_number is not None else "",
                    "seg_path": _relative(seg) if seg.exists() else "",
                }
            )
    return pd.DataFrame(rows)


def _relative(path: Path) -> str:
    try:
        return path.relative_to(paths.DATA).as_posix()
    except ValueError:
        return path.as_posix()


def absolute(path: str) -> Path:
    """Inverse of the manifest's relative paths."""
    p = Path(path)
    return p if p.is_absolute() else paths.DATA / p
