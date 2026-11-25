"""FastAPI application factory.

One process serves everything: the JSON API under ``/api`` and the built React app
(``frontend/dist``) for every other path, so the farmer only runs a single command.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api import router as api_router
from app.config import Settings
from app.db import init_db
from app.ratelimit import RateLimitMiddleware
from app.services.diseases import DiseaseLibrary
from app.services.inference import InferenceService


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the app. Tests pass custom ``Settings`` pointing at temporary folders."""
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        settings.ensure_dirs()
        app.state.session_factory = init_db(settings.db_url)
        app.state.inference = InferenceService.load(settings.model_dir)
        app.state.diseases = DiseaseLibrary.load(settings.diseases_file)
        yield

    app = FastAPI(
        title="CropDoc GB API",
        version=__version__,
        description="AI plant-disease scanner for Gilgit-Baltistan. General guidance only, not a diagnosis.",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["*"],
    )
    app.add_middleware(
        RateLimitMiddleware,
        per_minute=settings.rate_limit_per_minute,
        paths=("/api/predict", "/api/contribute"),
    )
    app.add_middleware(
        RateLimitMiddleware,
        per_minute=settings.live_rate_limit_per_minute,
        paths=("/api/predict/live",),
    )
    app.include_router(api_router, prefix="/api")
    _mount_frontend(app, settings.frontend_dist)
    return app


def _mount_frontend(app: FastAPI, dist: Path) -> None:
    """Serve the built single-page app; unknown paths fall back to index.html (client routing)."""
    index = dist / "index.html"
    if not index.exists():

        @app.get("/", include_in_schema=False)
        def frontend_missing() -> JSONResponse:
            return JSONResponse(
                {
                    "detail": "Frontend not built. Run `make web-build` (or use the packaged zip). API docs: /docs"
                }
            )

        return

    assets = dist / "assets"
    if assets.exists():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str) -> FileResponse:
        if full_path.startswith("api/"):
            return JSONResponse({"detail": "Not Found"}, status_code=404)  # type: ignore[return-value]
        candidate = (dist / full_path).resolve()
        if full_path and candidate.is_file() and dist.resolve() in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(index)


app = create_app()
