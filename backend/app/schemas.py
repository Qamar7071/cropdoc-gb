"""Pydantic models for API requests and responses (also used to generate the OpenAPI docs)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

Status = Literal["confident", "low_confidence", "not_a_leaf_or_unsupported_crop", "retake_photo"]

GB_DISTRICTS = [
    "Skardu",
    "Gilgit",
    "Hunza",
    "Nagar",
    "Ghizer",
    "Astore",
    "Diamer",
    "Ghanche",
    "Shigar",
    "Kharmang",
]


class Health(BaseModel):
    status: Literal["ok"] = "ok"
    app_version: str
    model_loaded: bool
    model_version: str | None = None
    reason: str | None = Field(None, description="Why the model is not loaded (with fix instructions).")
    num_classes: int = 0
    metrics: dict[str, Any] = Field(
        default_factory=dict, description="Copied from models/active/model_card.json."
    )
    thresholds_provisional: bool | None = None
    temporary_storage: bool = Field(
        False, description="True on serverless hosts where saved scans can disappear after a restart."
    )


class ClassOut(BaseModel):
    id: str
    crop: str
    disease: str
    healthy: bool


class ModelInfo(BaseModel):
    model_loaded: bool
    model_version: str | None = None
    classes: list[ClassOut] = Field(default_factory=list)
    crops: list[str] = Field(default_factory=list)
    districts: list[str] = Field(default_factory=lambda: list(GB_DISTRICTS))
    model_card: dict[str, Any] = Field(default_factory=dict)
    calibration: dict[str, Any] = Field(default_factory=dict)


class TopPrediction(BaseModel):
    class_id: str
    crop: str
    disease: str
    probability: float


class Bilingual(BaseModel):
    en: str = ""
    ur: str = ""


class BilingualList(BaseModel):
    en: list[str] = Field(default_factory=list)
    ur: list[str] = Field(default_factory=list)


class DiseaseReport(BaseModel):
    """Bilingual knowledge for the result screen (from diseases.json + diseases_ur.json, never from the photo)."""

    id: str
    crop: Bilingual
    name: Bilingual
    category: str = ""
    healthy: bool = False
    pathogen: str = ""
    description: Bilingual
    risk_level: str = Field(
        "", description="General loss potential of the disease (low/medium/high/none), from sources."
    )
    risk_reason: Bilingual
    symptoms_early: BilingualList
    symptoms_advanced: BilingualList
    spread: Bilingual
    causes: BilingualList
    immediate_actions: BilingualList
    prevention: BilingualList
    treatment_categories: BilingualList
    call_expert_when: BilingualList
    extension_fallback: Bilingual
    sources: list[str] = Field(default_factory=list)
    needs_review: bool = True
    urdu_needs_review: bool = True


class QualityReport(BaseModel):
    """Is the photo good enough to analyse? (thresholds from validation photos: models/active/quality.json)"""

    checked: bool = False
    ok: bool = True
    issues: list[str] = Field(default_factory=list, description="too_dark, too_bright, blurry")
    brightness: float | None = None
    sharpness: float | None = None


class DiseaseBrief(BaseModel):
    id: str
    description: str = ""
    category: str = ""
    recommendations: list[str] = Field(default_factory=list)
    needs_review: bool = True
    report: DiseaseReport | None = None


class PredictResponse(BaseModel):
    scan_id: str | None = Field(None, description="Set when the scan was saved to history.")
    saved: bool
    status: Status
    class_id: str
    crop: str
    disease: str
    healthy: bool
    confidence: float = Field(..., description="Calibrated probability of the top class.")
    top3: list[TopPrediction]
    disease_info: DiseaseBrief
    gradcam_png: str = Field(..., description="Base64 PNG: Grad-CAM heatmap blended over the model's view.")
    heatmap_png: str = Field(..., description="Base64 PNG: heatmap only (for the opacity slider).")
    model_view_jpeg: str = Field(..., description="Base64 JPEG: the centre crop the model actually saw.")
    scores: dict[str, float]
    thresholds: dict[str, Any]
    quality: QualityReport = Field(default_factory=QualityReport)
    crop_hint: str | None = None
    district: str | None = None
    model_version: str
    disclaimer: str = "General guidance only, not a diagnosis. Please consult an agriculture expert."


class LivePredictResponse(BaseModel):
    """Lightweight answer for one live-camera frame. Never saved; no full-size images."""

    status: Status
    class_id: str
    crop: str
    disease: str
    healthy: bool
    confidence: float = Field(..., description="Calibrated probability of the top class.")
    top3: list[TopPrediction]
    disease_info: DiseaseBrief
    heatmap_png: str = Field(
        ..., description="Base64 PNG (RGBA, 112 px): Grad-CAM with transparency, to draw over the camera."
    )
    quality: QualityReport = Field(default_factory=QualityReport)
    crop_hint: str | None = None
    model_version: str
    inference_ms: float = Field(..., description="Server time spent on this frame, in milliseconds.")
    disclaimer: str = "General guidance only, not a diagnosis. Please consult an agriculture expert."


class NetworkInfo(BaseModel):
    """How to open the app from a phone on the same Wi-Fi (filled in by `run.py --phone`)."""

    phone_mode: bool
    urls: list[str] = Field(default_factory=list)


class FeedbackIn(BaseModel):
    correct: bool
    correct_class_id: str | None = Field(None, description="Required when correct is false.")


class FeedbackOut(BaseModel):
    correct: bool
    correct_class_id: str | None = None
    created_at: datetime


class ScanSummary(BaseModel):
    id: str
    created_at: datetime
    class_id: str
    crop: str
    disease: str
    confidence: float
    status: str
    district: str | None = None
    thumbnail_url: str
    feedback: FeedbackOut | None = None


class ScanDetail(ScanSummary):
    top3: list[TopPrediction]
    crop_hint: str | None = None
    model_version: str
    image_url: str
    gradcam_url: str | None = None


class ScanPage(BaseModel):
    items: list[ScanSummary]
    total: int
    page: int
    page_size: int


class CountItem(BaseModel):
    key: str
    label: str
    count: int


class Stats(BaseModel):
    total_scans: int
    healthy_scans: int
    diseased_scans: int
    by_disease: list[CountItem]
    by_week: list[CountItem]
    by_district: list[CountItem]
    feedback: dict[str, int]
    source: str = "Computed only from scans saved on this device."


class ContributeOut(BaseModel):
    saved: bool
    id: str
