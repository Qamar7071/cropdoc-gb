"""All API routes, mounted under /api by app.main."""

from fastapi import APIRouter

from app.api import contribute, diseases, field_intel, health, predict, scans, stats

router = APIRouter()
for module in (health, predict, scans, stats, diseases, field_intel, contribute):
    router.include_router(module.router)
