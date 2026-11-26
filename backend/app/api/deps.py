"""Shared FastAPI dependencies (settings, DB session, model, disease library)."""

from __future__ import annotations

from collections.abc import Iterator

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from app.config import Settings
from app.services.diseases import DiseaseLibrary
from app.services.inference import InferenceService


class StartupFailed(Exception):
    """The app could not finish starting (folders, database or model); the message says why."""


def startup_help(exc: Exception) -> str:
    return (
        f"The server could not start: {type(exc).__name__}: {exc}. "
        "Online hosts: see docs/deploy.md. On your computer: run start.bat / start.sh again."
    )


def _ready(request: Request):
    """App state, loading it on first use if the host skipped the start-up (lifespan) step."""
    from app.main import ensure_ready  # local import: app.main imports this module's routers

    try:
        ensure_ready(request.app)
    except Exception as exc:
        raise StartupFailed(startup_help(exc)) from exc
    return request.app.state


def _ready_or_503(request: Request):
    try:
        return _ready(request)
    except StartupFailed as exc:
        raise HTTPException(503, str(exc)) from exc


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_inference(request: Request) -> InferenceService:
    """Never raises: a failed start-up becomes a not-loaded model with the reason (shown by /api/health)."""
    try:
        return _ready(request).inference
    except StartupFailed as exc:
        return InferenceService(loaded=False, reason=str(exc))


def get_diseases(request: Request) -> DiseaseLibrary:
    return _ready_or_503(request).diseases


def get_session(request: Request) -> Iterator[Session]:
    session = _ready_or_503(request).session_factory()
    try:
        yield session
    finally:
        session.close()
