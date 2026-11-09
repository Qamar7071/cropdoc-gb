"""Scan history: list/search/filter, detail, images, delete, feedback."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.api.deps import get_inference, get_session
from app.db import Scan
from app.schemas import FeedbackIn, FeedbackOut, ScanDetail, ScanPage, ScanSummary
from app.services import history
from app.services.inference import InferenceService

router = APIRouter(tags=["history"])


def _summary(scan: Scan) -> dict:
    feedback = None
    if scan.feedback is not None:
        feedback = FeedbackOut(
            correct=scan.feedback.correct,
            correct_class_id=scan.feedback.correct_class_id,
            created_at=scan.feedback.created_at,
        )
    return {
        "id": scan.id,
        "created_at": scan.created_at,
        "class_id": scan.class_id,
        "crop": scan.crop,
        "disease": scan.disease,
        "confidence": scan.confidence,
        "status": scan.status,
        "district": scan.district,
        "thumbnail_url": f"/api/scans/{scan.id}/thumbnail",
        "feedback": feedback,
    }


def _get_or_404(session: Session, scan_id: str) -> Scan:
    scan = history.get_scan(session, scan_id)
    if scan is None:
        raise HTTPException(404, "Scan not found.")
    return scan


@router.get("/scans", response_model=ScanPage)
def list_scans(
    q: str | None = Query(None, description="Search disease or crop name."),
    disease: str | None = Query(None, description="Exact class id, e.g. Potato___Early_blight."),
    crop: str | None = None,
    district: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: Session = Depends(get_session),
) -> ScanPage:
    rows, total = history.list_scans(session, q, disease, crop, district, date_from, date_to, page, page_size)
    return ScanPage(
        items=[ScanSummary(**_summary(s)) for s in rows], total=total, page=page, page_size=page_size
    )


@router.get("/scans/{scan_id}", response_model=ScanDetail)
def scan_detail(scan_id: str, session: Session = Depends(get_session)) -> ScanDetail:
    scan = _get_or_404(session, scan_id)
    return ScanDetail(
        **_summary(scan),
        top3=scan.top3,
        crop_hint=scan.crop_hint,
        model_version=scan.model_version,
        image_url=f"/api/scans/{scan.id}/image",
        gradcam_url=f"/api/scans/{scan.id}/gradcam" if scan.gradcam_png else None,
    )


@router.get("/scans/{scan_id}/image", response_class=Response)
def scan_image(scan_id: str, session: Session = Depends(get_session)) -> Response:
    return Response(_get_or_404(session, scan_id).image_jpeg, media_type="image/jpeg")


@router.get("/scans/{scan_id}/thumbnail", response_class=Response)
def scan_thumbnail(scan_id: str, session: Session = Depends(get_session)) -> Response:
    return Response(_get_or_404(session, scan_id).thumb_jpeg, media_type="image/jpeg")


@router.get("/scans/{scan_id}/gradcam", response_class=Response)
def scan_gradcam(scan_id: str, session: Session = Depends(get_session)) -> Response:
    scan = _get_or_404(session, scan_id)
    if not scan.gradcam_png:
        raise HTTPException(404, "No Grad-CAM stored for this scan.")
    return Response(scan.gradcam_png, media_type="image/png")


@router.delete("/scans/{scan_id}", status_code=204, response_class=Response)
def delete_scan(scan_id: str, session: Session = Depends(get_session)) -> Response:
    if not history.delete_scan(session, scan_id):
        raise HTTPException(404, "Scan not found.")
    return Response(status_code=204)


@router.post("/scans/{scan_id}/feedback", response_model=FeedbackOut)
def feedback(
    scan_id: str,
    body: FeedbackIn,
    session: Session = Depends(get_session),
    inference: InferenceService = Depends(get_inference),
) -> FeedbackOut:
    """'Was this correct?' Stored for future few-shot adaptation."""
    scan = _get_or_404(session, scan_id)
    if not body.correct:
        if not body.correct_class_id:
            raise HTTPException(422, "Please choose the correct class when the prediction was wrong.")
        if inference.loaded and inference.class_index(body.correct_class_id) is None:
            raise HTTPException(422, f"Unknown class '{body.correct_class_id}'.")
    saved = history.set_feedback(session, scan, body.correct, None if body.correct else body.correct_class_id)
    return FeedbackOut(
        correct=saved.correct, correct_class_id=saved.correct_class_id, created_at=saved.created_at
    )
