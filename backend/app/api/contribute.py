"""POST /api/contribute: opt-in field photo donation saved to a local inbox folder."""

from __future__ import annotations

import json
import re
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.api.deps import get_settings
from app.api.predict import read_upload, validate_choice
from app.config import Settings
from app.schemas import GB_DISTRICTS, ContributeOut
from app.services import gradcam
from app.services.images import ImageRejected, downscale, load_clean_image

router = APIRouter(tags=["research"])
SAFE_LABEL = re.compile(r"[^A-Za-z0-9_(),.\- ]+")


@router.post("/contribute", response_model=ContributeOut)
async def contribute(
    image: UploadFile = File(...),
    label: str = Form(..., description="Crop + disease as you believe it is (or 'unknown')."),
    consent: bool = Form(..., description="Must be true: you agree the photo may be used for research."),
    district: str | None = Form(None),
    settings: Settings = Depends(get_settings),
) -> ContributeOut:
    if not consent:
        raise HTTPException(400, "Consent is required to contribute a photo.")
    clean_label = SAFE_LABEL.sub("", label).strip()[:80] or "unknown"
    district_name = validate_choice(district, GB_DISTRICTS, "district")
    data = await read_upload(image, settings.max_upload_bytes)
    try:
        clean = load_clean_image(data, settings.max_upload_bytes, settings.max_image_pixels)
    except ImageRejected as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc

    contribution_id = uuid.uuid4().hex
    folder = settings.inbox_dir / clean_label.replace(" ", "_")
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{contribution_id}.jpg").write_bytes(gradcam.jpeg_bytes(downscale(clean, 1600), quality=92))
    (folder / f"{contribution_id}.json").write_text(
        json.dumps(
            {
                "id": contribution_id,
                "label": clean_label,
                "district": district_name,
                "consent": True,
                "received_utc": datetime.now(UTC).isoformat(timespec="seconds"),
                "note": "Unverified label. Must be checked by an expert before use in any test set.",
            },
            indent=2,
        )
    )
    return ContributeOut(saved=True, id=contribution_id)
