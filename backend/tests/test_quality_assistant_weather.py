"""Photo-quality gate, the grounded assistant and the weather proxy."""

from __future__ import annotations

import io
import json
import shutil
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageFilter

from app.config import Settings
from app.main import create_app
from app.services.assistant import SYSTEM_PROMPT, Assistant, AssistantConfig, answer_language, detect_language
from app.services.quality import QualityThresholds, measure
from app.services.weather import WeatherService, advisories
from tests.conftest import image_bytes


# ---------------------------------------------------------------------------- quality
@pytest.fixture
def quality_model_dir(tmp_path, tiny_model_dir):
    folder = tmp_path / "model"
    shutil.copytree(tiny_model_dir, folder)
    (folder / "quality.json").write_text(
        json.dumps(
            {
                "thresholds": {"min_brightness": 40, "max_brightness": 230, "min_sharpness": 30},
                "source": "test",
            }
        )
    )
    return folder


def _photo(kind: str) -> bytes:
    image = Image.open(io.BytesIO(image_bytes(size=(320, 320))))
    if kind == "dark":
        image = image.point(lambda v: v // 12)
    if kind == "blur":
        image = image.filter(ImageFilter.GaussianBlur(12))
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=95)
    return buffer.getvalue()


def test_quality_measures_dark_and_blurry_photos():
    sharp = measure(Image.open(io.BytesIO(_photo("ok"))))
    dark = measure(Image.open(io.BytesIO(_photo("dark"))))
    blurry = measure(Image.open(io.BytesIO(_photo("blur"))))
    assert dark["brightness"] < sharp["brightness"] / 5
    assert blurry["sharpness"] < sharp["sharpness"] / 10


def test_without_thresholds_file_the_check_is_skipped(tmp_path):
    assert QualityThresholds.load(tmp_path / "missing.json").assess(Image.new("RGB", (50, 50))) == {
        "checked": False,
        "ok": True,
        "issues": [],
    }


def _client(tmp_path, model_dir, **overrides) -> TestClient:
    settings = Settings(
        model_dir=model_dir,
        data_dir=tmp_path / "d",
        inbox_dir=tmp_path / "i",
        frontend_dist=tmp_path / "nodist",
        rate_limit_per_minute=1000,
        **overrides,
    )
    client = TestClient(create_app(settings))
    client.__enter__()
    return client


def test_poor_photo_asks_for_a_retake_and_is_not_saved(tmp_path, quality_model_dir):
    client = _client(tmp_path, quality_model_dir)
    for kind, issue in (("dark", "too_dark"), ("blur", "blurry")):
        body = client.post(
            "/api/predict", files={"image": ("l.jpg", _photo(kind), "image/jpeg")}, data={"save": "true"}
        ).json()
        assert body["status"] == "retake_photo" and issue in body["quality"]["issues"]
        assert body["saved"] is False
        live = client.post("/api/predict/live", files={"image": ("f.jpg", _photo(kind), "image/jpeg")}).json()
        assert live["status"] == "retake_photo"
    good = client.post(
        "/api/predict", files={"image": ("l.jpg", _photo("ok"), "image/jpeg")}, data={"save": "true"}
    ).json()
    assert good["quality"]["checked"] and good["quality"]["ok"] and good["saved"] is True
    assert client.get("/api/scans").json()["total"] == 1
    client.__exit__(None, None, None)


# ---------------------------------------------------------------------------- assistant
def _assistant(client=None, ai=False, monkeypatch=None) -> Assistant:
    from pathlib import Path

    from app.services.crops import CropLibrary
    from app.services.diseases import DiseaseLibrary

    data = Path(__file__).resolve().parents[1] / "app" / "data"
    if monkeypatch is not None:
        if ai:
            monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        else:
            monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
            monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    return Assistant(
        DiseaseLibrary.load(data / "diseases.json"),
        CropLibrary.load(data / "crops.json", data / "tips.json"),
        AssistantConfig(),
        client=client,
    )


def test_language_detection():
    assert detect_language("میری فصل کے پتے پیلے کیوں ہو رہے ہیں؟") == "ur"
    assert detect_language("What is the best way to protect tomato plants?") == "en"
    assert detect_language("tamatar ke pattay peelay hain") == "en"  # Roman Urdu is Latin script
    # ...but knowledge-base answers to Roman Urdu come in Urdu script, English questions stay English
    assert answer_language("tamatar ke pattay peelay hain") == "ur"
    assert answer_language("meri fasal ke patte peele kyun ho rahe hain") == "ur"
    assert answer_language("Which fertilizer is suitable for my crop?") == "en"
    assert answer_language("How can I improve my crop yield?") == "en"


def test_retrieval_finds_the_right_knowledge_in_three_scripts(monkeypatch):
    a = _assistant(monkeypatch=monkeypatch)
    assert a.retrieve("گندم کی فصل کو بیماری سے کیسے بچاؤں؟")[0].id == "wheat"
    assert (
        a.retrieve("tamatar ke pattay murr rahe hain aur peelay hain")[0].id
        == "Tomato___Tomato_Yellow_Leaf_Curl_Virus"
    )
    assert a.retrieve("Which fertilizer is suitable for my crop?")[0].id == "fertilizer"
    assert a.retrieve("anything", class_id="Potato___Late_blight")[0].id == "Potato___Late_blight"
    # a question that names a disease gets that disease first, not the general crop page
    assert a.retrieve("How do I protect tomato plants from late blight?")[0].id == "Tomato___Late_blight"


def test_offline_answers_are_short_and_use_the_farmers_language(monkeypatch):
    a = _assistant(monkeypatch=monkeypatch)
    urdu = a.answer([{"role": "user", "content": "گندم کی فصل کو بیماری سے کیسے بچاؤں؟"}])["reply"]
    assert "Prevention" not in urdu and "Seasonal care" not in urdu and "بچاؤ" in urdu
    roman = a.answer([{"role": "user", "content": "tamatar ke pattay murr rahe hain aur peelay hain"}])
    assert roman["language"] == "ur" and "ٹماٹر" in roman["reply"]
    for question in (
        "گندم کی فصل کو بیماری سے کیسے بچاؤں؟",
        "How do I protect tomato plants from late blight?",
    ):
        assert len(a.answer([{"role": "user", "content": question}])["reply"]) < 900


def test_without_a_key_it_answers_from_the_knowledge_base_in_urdu(monkeypatch):
    result = _assistant(monkeypatch=monkeypatch).answer(
        [{"role": "user", "content": "گندم کی فصل کو بیماری سے کیسے بچاؤں؟"}]
    )
    assert result["mode"] == "knowledge_base" and result["notice"] == "ai_not_configured"
    assert result["language"] == "ur" and "گندم" in result["reply"]
    assert result["sources"] and result["related"][0]["id"] == "wheat"


class FakeClaude:
    def __init__(self, text="Remove infected leaves.", stop_reason="end_turn", error=None):
        self.calls, self.text, self.stop_reason, self.error = [], text, stop_reason, error
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        blocks = [SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=self.text)]
        return SimpleNamespace(content=blocks, stop_reason=self.stop_reason)


def test_ai_mode_sends_grounded_safe_request(monkeypatch):
    fake = FakeClaude("Check the lower leaves first.")
    a = _assistant(client=fake, ai=True, monkeypatch=monkeypatch)
    history = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi! Which crop?"},
        {"role": "user", "content": "My potato leaves have dark wet patches"},
    ]
    result = a.answer(history, class_id="Potato___Late_blight")
    assert result["mode"] == "ai" and result["reply"] == "Check the lower leaves first."
    call = fake.calls[0]
    assert call["model"] == "claude-opus-5-5" and call["fallbacks"] == "default"
    assert (
        call["output_config"] == {"effort": "medium"} and "server-side-fallback-2026-07-01" in call["betas"]
    )
    assert (
        "Never name a pesticide" in call["system"][0]["text"] and call["system"][0]["text"] == SYSTEM_PROMPT
    )
    last = call["messages"][-1]["content"]
    assert 'id="Potato___Late_blight"' in last and last.endswith("My potato leaves have dark wet patches")
    assert [m["role"] for m in call["messages"]] == ["user", "assistant", "user"]


def test_ai_failure_or_refusal_never_breaks_the_answer(monkeypatch):
    broken = _assistant(
        client=FakeClaude(error=RuntimeError("network down")), ai=True, monkeypatch=monkeypatch
    )
    result = broken.answer([{"role": "user", "content": "tomato late blight"}])
    assert result["mode"] == "knowledge_base" and result["notice"] == "ai_unavailable" and result["reply"]
    refused = _assistant(client=FakeClaude(stop_reason="refusal", text=""), ai=True, monkeypatch=monkeypatch)
    assert "crops" in refused.answer([{"role": "user", "content": "something unrelated"}])["reply"]


def test_assistant_api_validates_and_answers(tmp_path, tiny_model_dir, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    client = _client(tmp_path, tiny_model_dir)
    status = client.get("/api/assistant/status").json()
    assert status["ai_available"] is False and status["privacy"]["ur"]
    ok = client.post(
        "/api/assistant/chat",
        json={"messages": [{"role": "user", "content": "How do I stop late blight on potatoes?"}]},
    )
    assert ok.status_code == 200 and ok.json()["mode"] == "knowledge_base"
    assert (
        client.post(
            "/api/assistant/chat", json={"messages": [{"role": "assistant", "content": "hi"}]}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/assistant/chat", json={"messages": [{"role": "user", "content": "x" * 3000}]}
        ).status_code
        == 422
    )
    client.__exit__(None, None, None)


# ---------------------------------------------------------------------------- weather
FORECAST = {
    "current": {
        "temperature_2m": 18.2,
        "relative_humidity_2m": 71,
        "precipitation": 0.0,
        "weather_code": 2,
        "wind_speed_10m": 9,
    },
    "daily": {
        "time": ["2026-11-26", "2026-11-27", "2026-11-28"],
        "weather_code": [61, 3, 0],
        "temperature_2m_max": [19, 17, 20],
        "temperature_2m_min": [6, 1, 4],
        "precipitation_sum": [4.2, 0, 0],
        "precipitation_probability_max": [80, 20, 5],
    },
}


def test_weather_forecast_rounds_location_caches_and_advises():
    calls = []

    def fake_fetch(url, params, timeout=6.0):
        calls.append((url, params))
        if "geocoding" in url:
            return {"results": [{"name": "Skardu", "latitude": 35.2971, "longitude": 75.6333}]}
        return FORECAST

    service = WeatherService(fetch=fake_fetch)
    result = service.forecast(district="Skardu")
    assert result["available"] and result["place"] == "Skardu"
    assert (result["latitude"], result["longitude"]) == (35.3, 75.6)  # rounded to ~10 km
    assert result["current"]["summary"]["ur"] and len(result["daily"]) == 3
    assert any("Rain" in a["en"] for a in result["advisories"]) and any(
        "frost" in a["en"] for a in result["advisories"]
    )
    assert result["attribution"].startswith("Weather data by Open-Meteo")
    service.forecast(district="Skardu")
    assert len(calls) == 2  # geocode + forecast once; second call served from cache


def test_weather_offline_or_disabled_is_reported_not_guessed():
    def offline(url, params, timeout=6.0):
        raise OSError("no network")

    assert WeatherService(fetch=offline).forecast(lat=35.9, lon=74.3) == {
        "available": False,
        "reason": "unreachable",
        "detail": "OSError",
    }
    assert WeatherService(enabled=False).forecast(district="Gilgit")["available"] is False
    assert advisories(
        [{"precipitation_probability": 0, "precipitation_mm": 0, "temp_min": 10, "temp_max": 25}]
    )[0]["en"].startswith("No rain")


def test_weather_endpoint(tmp_path, tiny_model_dir):
    client = _client(tmp_path, tiny_model_dir, weather_enabled=False)
    assert client.get("/api/weather?district=Gilgit").json() == {"available": False, "reason": "disabled"}
    assert client.get("/api/weather?lat=200&lon=0").status_code == 422
    client.__exit__(None, None, None)
