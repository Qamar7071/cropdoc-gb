"""GET /api/stats: dashboard numbers from real saved scans only."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_session
from app.schemas import Stats
from app.services.stats import compute_stats

router = APIRouter(tags=["stats"])


@router.get("/stats", response_model=Stats)
def stats(session: Session = Depends(get_session)) -> Stats:
    return Stats(**compute_stats(session))
