"""All API routes, mounted under /api by app.main."""

from fastapi import APIRouter

from app.api import (
    assistant,
    contribute,
    crops,
    diseases,
    field_intel,
    health,
    predict,
    scans,
    stats,
    weather,
)

router = APIRouter()
for module in (health, predict, scans, stats, diseases, crops, assistant, weather, field_intel, contribute):
    router.include_router(module.router)
