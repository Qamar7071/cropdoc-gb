"""Weather for the farmer's area (Open-Meteo via this server; see services/weather.py)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_weather
from app.services.weather import WeatherService

router = APIRouter(tags=["weather"])


@router.get("/weather")
def weather(
    district: str | None = Query(None, max_length=60, description="District or town name in Pakistan"),
    lat: float | None = Query(None, ge=-90, le=90),
    lon: float | None = Query(None, ge=-180, le=180),
    service: WeatherService = Depends(get_weather),
) -> dict:
    """Current weather, 3-day forecast and general farming notes. ``available: false`` when offline."""
    return service.forecast(district=district, lat=lat, lon=lon)
