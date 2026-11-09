"""Shared helpers for the CPU research experiments."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image
from sklearn.metrics import accuracy_score, f1_score
from torch.utils.data import DataLoader

from cropdoc import paths
from cropdoc.data.classes import CLASS_IDS, class_info
from cropdoc.data.datasets import IMAGE_SUFFIXES, ManifestDataset
from cropdoc.data.transforms import eval_transform
from cropdoc.quick import load_split  # noqa: F401  (re-exported for the experiments)
from cropdoc.utils import get_logger

log = get_logger("cropdoc.research")

# PlantDoc folder → PlantVillage class id (all 28 PlantDoc classes have a counterpart)
PLANTDOC_TO_PV = {
    "Apple Scab Leaf": "Apple___Apple_scab",
    "Apple leaf": "Apple___healthy",
    "Apple rust leaf": "Apple___Cedar_apple_rust",
    "Bell_pepper leaf spot": "Pepper,_bell___Bacterial_spot",
    "Bell_pepper leaf": "Pepper,_bell___healthy",
    "Blueberry leaf": "Blueberry___healthy",
    "Cherry leaf": "Cherry_(including_sour)___healthy",
    "Corn Gray leaf spot": "Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot",
    "Corn leaf blight": "Corn_(maize)___Northern_Leaf_Blight",
    "Corn rust leaf": "Corn_(maize)___Common_rust_",
    "Peach leaf": "Peach___healthy",
    "Potato leaf early blight": "Potato___Early_blight",
    "Potato leaf late blight": "Potato___Late_blight",
    "Raspberry leaf": "Raspberry___healthy",
    "Soyabean leaf": "Soybean___healthy",
    "Squash Powdery mildew leaf": "Squash___Powdery_mildew",
    "Strawberry leaf": "Strawberry___healthy",
    "Tomato Early blight leaf": "Tomato___Early_blight",
    "Tomato Septoria leaf spot": "Tomato___Septoria_leaf_spot",
    "Tomato leaf bacterial spot": "Tomato___Bacterial_spot",
    "Tomato leaf late blight": "Tomato___Late_blight",
    "Tomato leaf mosaic virus": "Tomato___Tomato_mosaic_virus",
    "Tomato leaf yellow virus": "Tomato___Tomato_Yellow_Leaf_Curl_Virus",
    "Tomato leaf": "Tomato___healthy",
    "Tomato mold leaf": "Tomato___Leaf_Mold",
    "Tomato two spotted spider mites leaf": "Tomato___Spider_mites Two-spotted_spider_mite",
    "grape leaf black rot": "Grape___Black_rot",
    "grape leaf": "Grape___healthy",
}
LABEL_OF = {c: i for i, c in enumerate(CLASS_IDS)}
CROP_OF_LABEL = np.array([class_info(c).crop for c in CLASS_IDS])


def readable(path: Path) -> bool:
    """True if Pillow can fully decode the image (PlantDoc contains a few broken files)."""
    try:
        with Image.open(path) as image:
            image.convert("RGB").load()
        return True
    except Exception:
        return False


@lru_cache(maxsize=1)
def plantdoc_frame() -> pd.DataFrame:
    """All readable PlantDoc photos with PlantVillage labels and PlantDoc's own train/test split."""
    rows = []
    for split in ("train", "test"):
        root = paths.PLANTDOC / split
        if not root.exists():
            continue
        for folder in sorted(p for p in root.iterdir() if p.is_dir()):
            class_id = PLANTDOC_TO_PV.get(folder.name)
            if class_id is None:
                continue
            for image in sorted(folder.iterdir()):
                if image.suffix.lower() in IMAGE_SUFFIXES and readable(image):
                    rows.append(
                        {
                            "path": str(image),
                            "folder": folder.name,
                            "class_id": class_id,
                            "label": LABEL_OF[class_id],
                            "split": split,
                        }
                    )
    return pd.DataFrame(rows)


def field_frame() -> pd.DataFrame:
    """GB field photos from data/field_test/<class_id>/ (empty frame if none collected yet)."""
    rows = []
    if paths.FIELD_TEST.exists():
        for folder in sorted(p for p in paths.FIELD_TEST.iterdir() if p.is_dir() and p.name in LABEL_OF):
            for image in sorted(folder.rglob("*")):
                if image.suffix.lower() in IMAGE_SUFFIXES and readable(image):
                    rows.append(
                        {
                            "path": str(image),
                            "class_id": folder.name,
                            "label": LABEL_OF[folder.name],
                            "photo_group": _photo_group(image.name),
                        }
                    )
    return pd.DataFrame(rows, columns=["path", "class_id", "label", "photo_group"])


def _photo_group(name: str) -> str:
    """'Skardu_P012_L03_20270614_2.jpg' → 'Skardu_P012_L03' (same leaf = same group)."""
    parts = Path(name).stem.split("_")
    return "_".join(parts[:3]) if len(parts) >= 3 else Path(name).stem


def imagenet_ood_frame() -> pd.DataFrame:
    """Everyday-object photos (ImageNet one-per-class sample), excluding plant/fungus synsets (n11–n13)."""
    root = paths.RAW / "imagenet-sample-images"
    rows = [
        {"path": str(p), "synset": p.name.split("_")[0]}
        for p in sorted(root.glob("*.JPEG"))
        if not p.name.startswith(("n11", "n12", "n13"))
    ]
    return pd.DataFrame(rows)


def onnx_outputs(model_path: Path, frame: pd.DataFrame, cams: bool = False, batch_size: int = 64):
    """(logits, cams or None) of an exported CamNet ONNX model for every row (eval transform)."""
    import onnxruntime as ort

    options = ort.SessionOptions()
    options.intra_op_num_threads = os.cpu_count() or 4
    session = ort.InferenceSession(str(model_path), options, providers=["CPUExecutionProvider"])
    names = ["logits", "cams"] if cams else ["logits"]
    loader = DataLoader(
        ManifestDataset(frame.assign(label=0), eval_transform()), batch_size=batch_size, num_workers=3
    )
    logit_chunks, cam_chunks = [], []
    for images, _, _ in loader:
        out = session.run(names, {"image": images.numpy()})
        logit_chunks.append(out[0])
        if cams:
            cam_chunks.append(out[1].astype(np.float16))
    return np.concatenate(logit_chunks), (np.concatenate(cam_chunks) if cams else None)


def metrics_on_present_classes(labels: np.ndarray, preds: np.ndarray) -> dict:
    """Accuracy + macro-F1 over the classes that actually occur in ``labels`` (38-way predictions)."""
    present = sorted(set(labels.tolist()))
    return {
        "n": int(len(labels)),
        "n_classes": len(present),
        "accuracy": float(accuracy_score(labels, preds)),
        "macro_f1": float(f1_score(labels, preds, labels=present, average="macro", zero_division=0)),
    }


def crop_hint_predictions(logits: np.ndarray, labels: np.ndarray) -> np.ndarray:
    """Predictions when the farmer tells the app the crop: only that crop's classes compete."""
    true_crops = CROP_OF_LABEL[labels]
    mask = CROP_OF_LABEL[None, :] == true_crops[:, None]
    return np.where(mask, logits, -np.inf).argmax(1)


def softmax(logits: np.ndarray, temperature: float = 1.0) -> np.ndarray:
    z = logits / temperature
    z = z - z.max(axis=1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=1, keepdims=True)


def energy(logits: np.ndarray) -> np.ndarray:
    peak = logits.max(axis=1, keepdims=True)
    return -(peak[:, 0] + np.log(np.exp(logits - peak).sum(axis=1)))
