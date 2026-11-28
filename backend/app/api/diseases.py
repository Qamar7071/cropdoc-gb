"""Disease library endpoints."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_diseases, get_settings
from app.config import Settings
from app.services.diseases import DiseaseLibrary, slug

router = APIRouter(tags=["diseases"])
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


def _images(dist: Path, class_id: str) -> list[str]:
    """Reference photos shipped with the frontend under /library/<slug>/ (public URLs)."""
    folder = dist / "library" / slug(class_id)
    if not folder.is_dir():
        return []
    return [
        f"/library/{folder.name}/{p.name}"
        for p in sorted(folder.iterdir())
        if p.suffix.lower() in IMAGE_SUFFIXES
    ]


@router.get("/diseases")
def list_diseases(
    crop: str | None = None,
    q: str | None = None,
    library: DiseaseLibrary = Depends(get_diseases),
    settings: Settings = Depends(get_settings),
) -> dict:
    items = []
    for entry in library.list(crop=crop, q=q):
        images = _images(settings.frontend_dist, entry["id"])
        items.append(
            {
                "id": entry["id"],
                "crop": entry.get("crop", ""),
                "disease": entry.get("disease", ""),
                "category": entry.get("category", ""),
                "description": entry.get("description", ""),
                "name_ur": library.urdu.get(entry["id"], {}).get("name", ""),
                "crop_ur": library.crop_ur(entry.get("crop", "")),
                "risk_level": entry.get("risk_level", ""),
                "needs_review": entry.get("needs_review", True),
                "image": images[0] if images else None,
            }
        )
    crops = sorted({e.get("crop", "") for e in library.entries.values()})
    return {"items": items, "crops": crops, "meta": library.meta}


@router.get("/diseases/{disease_id}")
def disease_detail(
    disease_id: str,
    library: DiseaseLibrary = Depends(get_diseases),
    settings: Settings = Depends(get_settings),
) -> dict:
    entry = library.get(disease_id)
    if entry is None:
        raise HTTPException(404, "Disease not found.")
    return {
        **entry,
        "images": _images(settings.frontend_dist, disease_id),
        "report": library.report(disease_id),
    }
