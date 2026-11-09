"""Saving, listing, filtering and deleting scans, plus farmer feedback."""

from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta
from typing import Any

from PIL import Image
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.db import Feedback, Scan
from app.services import gradcam
from app.services.images import downscale

IMAGE_MAX_SIDE = 512  # stored copy: enough for future few-shot fine-tuning, small on disk
THUMB_MAX_SIDE = 256


def save_scan(session: Session, result: dict[str, Any], image: Image.Image, district: str | None) -> Scan:
    """Persist one prediction with EXIF-free image copies."""
    scan = Scan(
        id=uuid.uuid4().hex,
        class_id=result["class_id"],
        crop=result["crop"],
        disease=result["disease"],
        confidence=result["confidence"],
        status=result["status"],
        district=district,
        crop_hint=result.get("crop_hint"),
        top3=result["top3"],
        model_version=result["model_version"],
        image_jpeg=gradcam.jpeg_bytes(downscale(image, IMAGE_MAX_SIDE)),
        thumb_jpeg=gradcam.jpeg_bytes(downscale(image, THUMB_MAX_SIDE), quality=82),
        gradcam_png=gradcam.png_bytes(result["images"]["overlay"]),
    )
    session.add(scan)
    session.commit()
    return scan


def list_scans(
    session: Session,
    q: str | None = None,
    class_id: str | None = None,
    crop: str | None = None,
    district: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Scan], int]:
    """Filtered, newest-first page of scans and the total count."""
    query = select(Scan)
    if q:
        like = f"%{q.lower()}%"
        query = query.where(
            or_(
                func.lower(Scan.disease).like(like),
                func.lower(Scan.crop).like(like),
                func.lower(Scan.class_id).like(like),
            )
        )
    if class_id:
        query = query.where(Scan.class_id == class_id)
    if crop:
        query = query.where(func.lower(Scan.crop) == crop.lower())
    if district:
        query = query.where(Scan.district == district)
    if date_from:
        query = query.where(Scan.created_at >= datetime.combine(date_from, time.min))
    if date_to:
        query = query.where(Scan.created_at < datetime.combine(date_to + timedelta(days=1), time.min))
    total = session.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = session.scalars(
        query.options(selectinload(Scan.feedback))
        .order_by(Scan.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return list(rows), int(total)


def get_scan(session: Session, scan_id: str) -> Scan | None:
    """One scan by id (with feedback), or None."""
    return session.scalars(
        select(Scan).options(selectinload(Scan.feedback)).where(Scan.id == scan_id)
    ).first()


def delete_scan(session: Session, scan_id: str) -> bool:
    """Delete a scan (and its feedback). Returns False if it did not exist."""
    scan = session.get(Scan, scan_id)
    if scan is None:
        return False
    session.delete(scan)
    session.commit()
    return True


def set_feedback(session: Session, scan: Scan, correct: bool, correct_class_id: str | None) -> Feedback:
    """Create or replace the feedback for a scan."""
    if scan.feedback is None:
        scan.feedback = Feedback(correct=correct, correct_class_id=correct_class_id)
    else:
        scan.feedback.correct = correct
        scan.feedback.correct_class_id = correct_class_id
    session.commit()
    session.refresh(scan)
    return scan.feedback  # type: ignore[return-value]
