"""Shared FastAPI dependencies (settings, DB session, model, disease library)."""

from __future__ import annotations

from collections.abc import Iterator

from fastapi import Request
from sqlalchemy.orm import Session

from app.config import Settings
from app.services.diseases import DiseaseLibrary
from app.services.inference import InferenceService


def _ready(request: Request):
    """App state, loading it on first use if the host skipped the start-up (lifespan) step."""
    from app.main import ensure_ready  # local import: app.main imports this module's routers

    ensure_ready(request.app)
    return request.app.state


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_inference(request: Request) -> InferenceService:
    return _ready(request).inference


def get_diseases(request: Request) -> DiseaseLibrary:
    return _ready(request).diseases


def get_session(request: Request) -> Iterator[Session]:
    session = _ready(request).session_factory()
    try:
        yield session
    finally:
        session.close()
