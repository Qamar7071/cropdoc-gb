"""Live camera mode: /api/predict/live answers quickly, never saves, and has its own rate limit."""

from __future__ import annotations

import base64
import io

from PIL import Image

from tests.conftest import image_bytes


def live(client, data: bytes, **form):
    return client.post("/api/predict/live", files={"image": ("frame.jpg", data, "image/jpeg")}, data=form)


def test_live_without_model_returns_503(make_client):
    response = live(make_client(), image_bytes())
    assert response.status_code == 503
    assert "Model not loaded" in response.json()["detail"]


def test_live_returns_small_answer_and_never_saves(make_client, tiny_model_dir):
    client = make_client(tiny_model_dir)
    response = live(client, image_bytes(size=(384, 384)))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] in {"confident", "low_confidence", "not_a_leaf_or_unsupported_crop"}
    assert body["confidence"] == body["top3"][0]["probability"]
    assert body["disease_info"]["recommendations"]
    assert body["inference_ms"] >= 0
    assert "gradcam_png" not in body and "model_view_jpeg" not in body
    heat = Image.open(io.BytesIO(base64.b64decode(body["heatmap_png"])))
    assert heat.format == "PNG" and heat.mode == "RGBA" and heat.size == (112, 112)
    assert client.get("/api/scans").json()["total"] == 0


def test_live_matches_full_predict(make_client, tiny_model_dir):
    """Same model, calibration and thresholds as the full scanner."""
    client = make_client(tiny_model_dir)
    data = image_bytes()
    full = client.post(
        "/api/predict", files={"image": ("leaf.jpg", data, "image/jpeg")}, data={"save": "false"}
    ).json()
    quick = live(client, data).json()
    for key in ("status", "class_id", "top3"):
        assert quick[key] == full[key]
    assert abs(quick["confidence"] - full["confidence"]) < 1e-9


def test_live_crop_hint_and_validation(make_client, tiny_model_dir):
    client = make_client(tiny_model_dir)
    assert live(client, image_bytes(), crop_hint="tomato").json()["crop_hint"] == "Tomato"
    assert live(client, image_bytes(), crop_hint="banana").status_code == 422
    assert live(client, b"not an image").status_code in {400, 415, 422}


def test_live_has_its_own_rate_limit(make_client, tiny_model_dir):
    client = make_client(tiny_model_dir, rate_limit_per_minute=2, live_rate_limit_per_minute=5)
    codes = [live(client, image_bytes()).status_code for _ in range(7)]
    assert codes[:5] == [200] * 5 and codes[5:] == [429, 429]
    # live frames did not use up the photo scanner's bucket
    full = client.post("/api/predict", files={"image": ("leaf.jpg", image_bytes(), "image/jpeg")})
    assert full.status_code == 200


def test_network_info_off_by_default(make_client):
    assert make_client().get("/api/network").json() == {"phone_mode": False, "urls": []}


def test_network_info_in_phone_mode(make_client):
    client = make_client(phone_mode=True, public_urls=["https://192.168.1.20:8443"])
    assert client.get("/api/network").json() == {"phone_mode": True, "urls": ["https://192.168.1.20:8443"]}
