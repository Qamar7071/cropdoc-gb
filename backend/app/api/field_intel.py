"""GET /api/field-intelligence: research results read from results/*.json ("pending" if missing)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_settings
from app.config import Settings
from app.services.field_intel import load_sections

router = APIRouter(tags=["research"])


@router.get("/field-intelligence")
def field_intelligence(settings: Settings = Depends(get_settings)) -> dict:
    sections = load_sections(settings.results_dir)
    ready = sum(1 for s in sections.values() if s["status"] == "ready")
    return {"sections": sections, "ready": ready, "total": len(sections)}
