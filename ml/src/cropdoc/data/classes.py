"""The 38 PlantVillage classes with clean crop and disease names.

The class *id* is the PlantVillage folder name (e.g. ``Potato___Early_blight``); it never changes
and is used everywhere (model outputs, API, disease library, field-photo folders). The crop and
disease names are for people.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass

# folder name -> (crop, disease, category)
_CLASSES: dict[str, tuple[str, str, str]] = {
    "Apple___Apple_scab": ("Apple", "Apple scab", "fungal"),
    "Apple___Black_rot": ("Apple", "Black rot", "fungal"),
    "Apple___Cedar_apple_rust": ("Apple", "Cedar apple rust", "fungal"),
    "Apple___healthy": ("Apple", "Healthy", "healthy"),
    "Blueberry___healthy": ("Blueberry", "Healthy", "healthy"),
    "Cherry_(including_sour)___Powdery_mildew": ("Cherry", "Powdery mildew", "fungal"),
    "Cherry_(including_sour)___healthy": ("Cherry", "Healthy", "healthy"),
    "Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot": ("Corn", "Gray leaf spot", "fungal"),
    "Corn_(maize)___Common_rust_": ("Corn", "Common rust", "fungal"),
    "Corn_(maize)___Northern_Leaf_Blight": ("Corn", "Northern leaf blight", "fungal"),
    "Corn_(maize)___healthy": ("Corn", "Healthy", "healthy"),
    "Grape___Black_rot": ("Grape", "Black rot", "fungal"),
    "Grape___Esca_(Black_Measles)": ("Grape", "Esca (black measles)", "fungal"),
    "Grape___Leaf_blight_(Isariopsis_Leaf_Spot)": ("Grape", "Leaf blight (Isariopsis leaf spot)", "fungal"),
    "Grape___healthy": ("Grape", "Healthy", "healthy"),
    "Orange___Haunglongbing_(Citrus_greening)": ("Orange", "Huanglongbing (citrus greening)", "bacterial"),
    "Peach___Bacterial_spot": ("Peach", "Bacterial spot", "bacterial"),
    "Peach___healthy": ("Peach", "Healthy", "healthy"),
    "Pepper,_bell___Bacterial_spot": ("Bell pepper", "Bacterial spot", "bacterial"),
    "Pepper,_bell___healthy": ("Bell pepper", "Healthy", "healthy"),
    "Potato___Early_blight": ("Potato", "Early blight", "fungal"),
    "Potato___Late_blight": ("Potato", "Late blight", "oomycete"),
    "Potato___healthy": ("Potato", "Healthy", "healthy"),
    "Raspberry___healthy": ("Raspberry", "Healthy", "healthy"),
    "Soybean___healthy": ("Soybean", "Healthy", "healthy"),
    "Squash___Powdery_mildew": ("Squash", "Powdery mildew", "fungal"),
    "Strawberry___Leaf_scorch": ("Strawberry", "Leaf scorch", "fungal"),
    "Strawberry___healthy": ("Strawberry", "Healthy", "healthy"),
    "Tomato___Bacterial_spot": ("Tomato", "Bacterial spot", "bacterial"),
    "Tomato___Early_blight": ("Tomato", "Early blight", "fungal"),
    "Tomato___Late_blight": ("Tomato", "Late blight", "oomycete"),
    "Tomato___Leaf_Mold": ("Tomato", "Leaf mold", "fungal"),
    "Tomato___Septoria_leaf_spot": ("Tomato", "Septoria leaf spot", "fungal"),
    "Tomato___Spider_mites Two-spotted_spider_mite": ("Tomato", "Spider mites (two-spotted)", "pest"),
    "Tomato___Target_Spot": ("Tomato", "Target spot", "fungal"),
    "Tomato___Tomato_Yellow_Leaf_Curl_Virus": ("Tomato", "Yellow leaf curl virus", "viral"),
    "Tomato___Tomato_mosaic_virus": ("Tomato", "Mosaic virus", "viral"),
    "Tomato___healthy": ("Tomato", "Healthy", "healthy"),
}

CLASS_IDS: list[str] = sorted(_CLASSES)  # alphabetical = PlantVillage folder order = model output order


@dataclass(frozen=True)
class ClassInfo:
    """Human-friendly description of one model class."""

    id: str
    crop: str
    disease: str
    healthy: bool
    category: str


def class_info(class_id: str) -> ClassInfo:
    """Look up one class (raises KeyError for unknown ids)."""
    crop, disease, category = _CLASSES[class_id]
    return ClassInfo(class_id, crop, disease, category == "healthy", category)


def all_classes(class_ids: list[str] | None = None) -> list[ClassInfo]:
    """ClassInfo for the given ids (default: all 38, in model output order)."""
    return [class_info(c) for c in (class_ids or CLASS_IDS)]


def classes_json(class_ids: list[str] | None = None) -> dict:
    """The ``classes.json`` payload shipped next to the model (index order = output order)."""
    return {
        "classes": [
            {k: v for k, v in asdict(c).items() if k != "category"} for c in all_classes(class_ids)
        ]
    }


def crops(class_ids: list[str] | None = None) -> list[str]:
    """Sorted list of crop names."""
    return sorted({c.crop for c in all_classes(class_ids)})


def slug(class_id: str) -> str:
    """URL/folder-safe version of a class id ('Corn_(maize)___Common_rust_' → 'Corn_maize_Common_rust').

    Must match backend/app/services/diseases.py::slug (checked by a test).
    """
    return re.sub(r"[^A-Za-z0-9]+", "_", class_id).strip("_")
