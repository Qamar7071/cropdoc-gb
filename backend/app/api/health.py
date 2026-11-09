"""Health and model information."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app import __version__
from app.api.deps import get_inference
from app.schemas import ClassOut, Health, ModelInfo
from app.services.inference import InferenceService

router = APIRouter(tags=["health"])


@router.get("/health", response_model=Health)
def health(inference: InferenceService = Depends(get_inference)) -> Health:
    """Is the model loaded? Which version? Real metrics from model_card.json."""
    if not inference.loaded:
        return Health(app_version=__version__, model_loaded=False, reason=inference.reason)
    return Health(
        app_version=__version__,
        model_loaded=True,
        model_version=inference.version,
        num_classes=len(inference.classes),
        metrics=inference.model_card.get("metrics", {}),
        thresholds_provisional=inference.thresholds.provisional,
    )


@router.get("/model", response_model=ModelInfo)
def model_info(inference: InferenceService = Depends(get_inference)) -> ModelInfo:
    """Classes, supported crops, districts, full model card and calibration (for the UI)."""
    if not inference.loaded:
        return ModelInfo(model_loaded=False)
    return ModelInfo(
        model_loaded=True,
        model_version=inference.version,
        classes=[ClassOut(**vars(c)) for c in inference.classes],
        crops=inference.crops,
        model_card=inference.model_card,
        calibration=inference.calibration,
    )
