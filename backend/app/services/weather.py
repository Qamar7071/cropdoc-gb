"""Weather for the farmer's area from Open-Meteo (free, no key; data from national weather services).

Requests go through this backend, so the farmer's own IP address is not sent to the weather service,
and coordinates are rounded to about 10 km first. Results are cached for 30 minutes. Without internet
(or with CROPDOC_WEATHER=off) the API says the weather is unavailable; nothing is guessed.

The farming notes are simple, general rules of thumb (e.g. rain expected → do not spray, check leaves
after rain), clearly labelled as general guidance.
"""

from __future__ import annotations

import json
import threading
import time
import urllib.parse
import urllib.request
from typing import Any

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
CACHE_SECONDS = 30 * 60
ATTRIBUTION = "Weather data by Open-Meteo.com (CC BY 4.0)"

# WMO weather interpretation codes used by Open-Meteo → short descriptions
WEATHER_CODES = {
    0: ("Clear sky", "صاف آسمان"),
    1: ("Mostly clear", "زیادہ تر صاف"),
    2: ("Partly cloudy", "جزوی ابر آلود"),
    3: ("Cloudy", "ابر آلود"),
    45: ("Fog", "دھند"),
    48: ("Fog", "دھند"),
    51: ("Light drizzle", "ہلکی بوندا باندی"),
    53: ("Drizzle", "بوندا باندی"),
    55: ("Heavy drizzle", "تیز بوندا باندی"),
    56: ("Freezing drizzle", "جمنے والی بوندا باندی"),
    57: ("Freezing drizzle", "جمنے والی بوندا باندی"),
    61: ("Light rain", "ہلکی بارش"),
    63: ("Rain", "بارش"),
    65: ("Heavy rain", "تیز بارش"),
    66: ("Freezing rain", "جمنے والی بارش"),
    67: ("Freezing rain", "جمنے والی بارش"),
    71: ("Light snow", "ہلکی برف باری"),
    73: ("Snow", "برف باری"),
    75: ("Heavy snow", "شدید برف باری"),
    77: ("Snow grains", "برف کے دانے"),
    80: ("Rain showers", "بارش کی بوچھاڑ"),
    81: ("Rain showers", "بارش کی بوچھاڑ"),
    82: ("Heavy showers", "تیز بوچھاڑ"),
    85: ("Snow showers", "برف کی بوچھاڑ"),
    86: ("Snow showers", "برف کی بوچھاڑ"),
    95: ("Thunderstorm", "آندھی اور گرج چمک"),
    96: ("Thunderstorm with hail", "اولوں کے ساتھ طوفان"),
    99: ("Thunderstorm with hail", "اولوں کے ساتھ طوفان"),
}


def describe(code: int | None) -> dict[str, str]:
    en, ur = WEATHER_CODES.get(int(code) if code is not None else -1, ("Unknown", "نامعلوم"))
    return {"en": en, "ur": ur}


def _get_json(url: str, params: dict[str, Any], timeout: float = 6.0) -> dict:
    full = f"{url}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(full, headers={"User-Agent": "CropDoc-GB/1.2 (open-source farm app)"})
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed https hosts
        return json.loads(response.read().decode("utf-8"))


def advisories(daily: list[dict]) -> list[dict[str, str]]:
    """General farming notes from the next days' forecast (rules of thumb, not a disease forecast)."""
    notes = []
    rainy = any(
        (d.get("precipitation_probability") or 0) >= 50 or (d.get("precipitation_mm") or 0) >= 1
        for d in daily
    )
    if rainy:
        notes.append(
            {
                "en": "Rain is likely in the next days: do not spray before rain, and check leaves for new spots after it.",
                "ur": "آنے والے دنوں میں بارش کا امکان ہے: بارش سے پہلے اسپرے نہ کریں، اور بارش کے بعد پتوں پر نئے دھبے دیکھیں۔",
            }
        )
        notes.append(
            {
                "en": "Wet leaves help fungal diseases spread: water at the roots and keep drains open.",
                "ur": "گیلے پتے پھپھوندی کی بیماریاں پھیلاتے ہیں: جڑوں کے پاس پانی دیں اور نکاسی کھلی رکھیں۔",
            }
        )
    if any((d.get("temp_min") is not None and d["temp_min"] <= 2) for d in daily):
        notes.append(
            {
                "en": "Near-freezing nights are forecast: protect seedlings and young plants from frost.",
                "ur": "راتیں نقطۂ انجماد کے قریب ہوں گی: پنیری اور چھوٹے پودوں کو پالے سے بچائیں۔",
            }
        )
    if any((d.get("temp_max") is not None and d["temp_max"] >= 40) for d in daily):
        notes.append(
            {
                "en": "Very hot days are forecast: irrigate in the early morning or evening and watch for wilting and mites.",
                "ur": "بہت گرم دن متوقع ہیں: صبح سویرے یا شام کو آبپاشی کریں اور مرجھاہٹ اور جوؤں پر نظر رکھیں۔",
            }
        )
    if not notes:
        notes.append(
            {
                "en": "No rain or extreme temperatures expected: a good time for field work and weekly checks.",
                "ur": "بارش یا شدید درجہ حرارت متوقع نہیں: کھیت کے کام اور ہفتہ وار معائنے کے لیے اچھا وقت ہے۔",
            }
        )
    return notes


class WeatherService:
    def __init__(self, enabled: bool = True, fetch=_get_json):
        self.enabled = enabled
        self.fetch = fetch
        self._cache: dict[tuple, tuple[float, dict]] = {}
        self._places: dict[str, dict] = {}
        self._lock = threading.Lock()

    def locate(self, name: str) -> dict | None:
        key = name.strip().lower()
        if key in self._places:
            return self._places[key]
        data = self.fetch(
            GEOCODE_URL, {"name": name, "count": 1, "language": "en", "format": "json", "countryCode": "PK"}
        )
        results = data.get("results") or []
        if not results:
            return None
        place = {
            "name": results[0].get("name", name),
            "latitude": results[0]["latitude"],
            "longitude": results[0]["longitude"],
        }
        self._places[key] = place
        return place

    def forecast(
        self, *, district: str | None = None, lat: float | None = None, lon: float | None = None
    ) -> dict:
        if not self.enabled:
            return {"available": False, "reason": "disabled"}
        try:
            if district:
                place = self.locate(district)
                if place is None:
                    return {"available": False, "reason": "place_not_found"}
                lat, lon, name = place["latitude"], place["longitude"], place["name"]
            elif lat is not None and lon is not None:
                name = None
            else:
                return {"available": False, "reason": "no_location"}
            lat, lon = (
                round(float(lat), 1),
                round(float(lon), 1),
            )  # ~10 km: enough for weather, less precise for privacy
            key = (lat, lon)
            with self._lock:
                hit = self._cache.get(key)
                if hit and time.time() - hit[0] < CACHE_SECONDS:
                    return {**hit[1], "place": name or hit[1].get("place")}
            data = self.fetch(
                FORECAST_URL,
                {
                    "latitude": lat,
                    "longitude": lon,
                    "current": "temperature_2m,relative_humidity_2m,precipitation,weather_code,wind_speed_10m",
                    "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max",
                    "timezone": "auto",
                    "forecast_days": 3,
                },
            )
            current = data.get("current", {})
            d = data.get("daily", {})
            daily = [
                {
                    "date": date,
                    "summary": describe((d.get("weather_code") or [None])[i]),
                    "temp_max": (d.get("temperature_2m_max") or [None])[i],
                    "temp_min": (d.get("temperature_2m_min") or [None])[i],
                    "precipitation_mm": (d.get("precipitation_sum") or [None])[i],
                    "precipitation_probability": (d.get("precipitation_probability_max") or [None])[i],
                }
                for i, date in enumerate(d.get("time", []))
            ]
            result = {
                "available": True,
                "place": name,
                "latitude": lat,
                "longitude": lon,
                "current": {
                    "temperature": current.get("temperature_2m"),
                    "humidity": current.get("relative_humidity_2m"),
                    "precipitation_mm": current.get("precipitation"),
                    "wind_kmh": current.get("wind_speed_10m"),
                    "summary": describe(current.get("weather_code")),
                },
                "daily": daily,
                "advisories": advisories(daily),
                "advisory_note": {
                    "en": "General guidance from the forecast, not a disease forecast.",
                    "ur": "پیش گوئی سے عمومی رہنمائی، بیماری کی پیش گوئی نہیں۔",
                },
                "attribution": ATTRIBUTION,
                "fetched_at": int(time.time()),
            }
            with self._lock:
                self._cache[key] = (time.time(), result)
            return result
        except Exception as exc:  # noqa: BLE001 - offline / service down → say so, never guess
            return {"available": False, "reason": "unreachable", "detail": type(exc).__name__}
