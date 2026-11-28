"""POST /api/predict: photo in, prediction + Grad-CAM out (optionally saved to history).

POST /api/predict/live: one camera frame in, a small answer out (live scanner, never saved).
"""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_diseases, get_inference, get_quality, get_session, get_settings
from app.config import Settings
from app.schemas import GB_DISTRICTS, DiseaseBrief, LivePredictResponse, PredictResponse
from app.services import gradcam, history
from app.services.diseases import DiseaseLibrary
from app.services.images import ImageRejected, load_clean_image
from app.services.inference import InferenceService
from app.services.quality import QualityThresholds

router = APIRouter(tags=["predict"])


async def read_upload(upload: UploadFile, max_bytes: int) -> bytes:
    """Read at most max_bytes + 1 bytes so huge uploads are rejected without loading them fully."""
    data = await upload.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise HTTPException(413, f"File too large: max {max_bytes // (1024 * 1024)} MB.")
    return data


def disease_brief(diseases: DiseaseLibrary, class_id: str) -> DiseaseBrief:
    """Short English fields (kept for older clients) + the full bilingual report."""
    entry = diseases.get(class_id) or {}
    return DiseaseBrief(
        id=class_id,
        description=entry.get("description", ""),
        category=entry.get("category", ""),
        recommendations=diseases.recommendations(class_id),
        needs_review=bool(entry.get("needs_review", True)),
        report=diseases.report(class_id) if entry else None,
    )


def validate_choice(value: str | None, allowed: list[str], field: str) -> str | None:
    """Empty → None; otherwise must match an allowed value (case-insensitive)."""
    if value is None or not value.strip():
        return None
    for option in allowed:
        if option.lower() == value.strip().lower():
            return option
    raise HTTPException(422, f"Unknown {field} '{value}'. Allowed: {', '.join(allowed)}")


@router.post("/predict", response_model=PredictResponse)
async def predict(
    image: UploadFile = File(..., description="Leaf photo, JPG or PNG, max 5 MB."),
    crop_hint: str | None = Form(None, description="Optional crop name; only that crop's classes compete."),
    district: str | None = Form(None, description="Optional Gilgit-Baltistan district."),
    save: bool = Form(True, description="Save this scan to history (thumbnail + result)."),
    settings: Settings = Depends(get_settings),
    inference: InferenceService = Depends(get_inference),
    diseases: DiseaseLibrary = Depends(get_diseases),
    quality_limits: QualityThresholds = Depends(get_quality),
    session: Session = Depends(get_session),
) -> PredictResponse:
    """Classify a leaf photo. Never returns a made-up result: 503 if no model is loaded."""
    if not inference.loaded:
        raise HTTPException(503, inference.reason)
    data = await read_upload(image, settings.max_upload_bytes)
    try:
        clean = load_clean_image(data, settings.max_upload_bytes, settings.max_image_pixels)
    except ImageRejected as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc

    hint = validate_choice(crop_hint, inference.crops, "crop_hint")
    district_name = validate_choice(district, GB_DISTRICTS, "district")
    result = inference.predict(clean, crop_hint=hint)
    quality = quality_limits.assess(clean)
    if not quality["ok"]:
        # never show (or store) a disease for a photo that cannot be analysed reliably
        result["status"] = "retake_photo"

    scan_id = None
    if save and result["status"] != "retake_photo":
        scan_id = history.save_scan(session, result, clean, district_name).id

    images = result["images"]
    return PredictResponse(
        scan_id=scan_id,
        saved=scan_id is not None,
        status=result["status"],
        class_id=result["class_id"],
        crop=result["crop"],
        disease=result["disease"],
        healthy=result["healthy"],
        confidence=result["confidence"],
        top3=result["top3"],
        disease_info=disease_brief(diseases, result["class_id"]),
        gradcam_png=gradcam.b64(gradcam.png_bytes(images["overlay"])),
        heatmap_png=gradcam.b64(gradcam.png_bytes(images["heatmap"])),
        model_view_jpeg=gradcam.b64(gradcam.jpeg_bytes(images["model_view"])),
        scores=result["scores"],
        thresholds=result["thresholds"],
        quality=quality,
        crop_hint=hint,
        district=district_name,
        model_version=result["model_version"],
    )


LIVE_HEATMAP_SIZE = (112, 112)


@router.post("/predict/live", response_model=LivePredictResponse)
async def predict_live(
    image: UploadFile = File(..., description="One camera frame (JPEG/PNG), ideally a ~384 px square."),
    crop_hint: str | None = Form(None, description="Optional crop name; only that crop's classes compete."),
    settings: Settings = Depends(get_settings),
    inference: InferenceService = Depends(get_inference),
    diseases: DiseaseLibrary = Depends(get_diseases),
    quality_limits: QualityThresholds = Depends(get_quality),
) -> LivePredictResponse:
    """Classify one live-camera frame. Same model, calibration and safety thresholds as /predict,
    but nothing is stored and only a small transparent heatmap is returned, so it is fast enough
    to call about twice a second from a phone."""
    if not inference.loaded:
        raise HTTPException(503, inference.reason)
    started = time.perf_counter()
    data = await read_upload(image, settings.max_upload_bytes)
    try:
        clean = load_clean_image(data, settings.max_upload_bytes, settings.max_image_pixels)
    except ImageRejected as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc

    hint = validate_choice(crop_hint, inference.crops, "crop_hint")
    result = inference.predict(clean, crop_hint=hint)
    quality = quality_limits.assess(clean)
    if not quality["ok"]:
        result["status"] = "retake_photo"
    heat = gradcam.heatmap_rgba(result["cam"], LIVE_HEATMAP_SIZE)
    return LivePredictResponse(
        status=result["status"],
        class_id=result["class_id"],
        crop=result["crop"],
        disease=result["disease"],
        healthy=result["healthy"],
        confidence=result["confidence"],
        top3=result["top3"],
        disease_info=disease_brief(diseases, result["class_id"]),
        heatmap_png=gradcam.b64(gradcam.png_bytes(heat)),
        quality=quality,
        crop_hint=hint,
        model_version=result["model_version"],
        inference_ms=round((time.perf_counter() - started) * 1000, 1),
    )
