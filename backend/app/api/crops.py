"""Crop information pages and farming tips (English + Urdu)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_crops, get_diseases
from app.services.crops import CropLibrary
from app.services.diseases import DiseaseLibrary

router = APIRouter(tags=["crops"])


@router.get("/crops")
def list_crops(library: CropLibrary = Depends(get_crops)) -> dict:
    """Short cards for the crop information section."""
    items = [
        {
            "id": c["id"],
            "name": c["name"],
            "season": c["season"],
            "summary": c["summary"],
            "scanner_supported": bool(c.get("scanner_classes")),
            "diseases": [d["name"] for d in c.get("diseases", [])],
        }
        for c in library.crops
    ]
    return {"items": items, "meta": library.meta}


@router.get("/crops/{crop_id}")
def crop_detail(
    crop_id: str, library: CropLibrary = Depends(get_crops), diseases: DiseaseLibrary = Depends(get_diseases)
) -> dict:
    crop = library.get(crop_id)
    if crop is None:
        raise HTTPException(404, "Crop not found.")
    scanner = [
        {
            "id": cid,
            "name": {
                "en": diseases.get(cid).get("disease", ""),
                "ur": diseases.urdu.get(cid, {}).get("name", ""),
            },
        }
        for cid in crop.get("scanner_classes", [])
        if diseases.get(cid)
    ]
    return {**crop, "scanner_diseases": scanner, "meta": library.meta}


@router.get("/tips")
def tips(library: CropLibrary = Depends(get_crops)) -> dict:
    return {"items": library.tips, "meta": library.tips_meta}
