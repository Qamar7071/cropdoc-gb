"""Shared FastAPI dependencies (settings, DB session, model, disease library)."""

from __future__ import annotations

from collections.abc import Iterator

from fastapi import Request
from sqlalchemy.orm import Session

from app.config import Settings
from app.services.diseases import DiseaseLibrary
from app.services.inference import InferenceService


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_inference(request: Request) -> InferenceService:
    return request.app.state.inference


def get_diseases(request: Request) -> DiseaseLibrary:
    return request.app.state.diseases


def get_session(request: Request) -> Iterator[Session]:
    session = request.app.state.session_factory()
    try:
        yield session
    finally:
        session.close()
