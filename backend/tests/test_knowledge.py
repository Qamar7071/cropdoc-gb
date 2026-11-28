"""Bilingual knowledge: every disease has a complete Urdu layer; crops and tips are sourced and safe."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from app.config import Settings
from app.main import create_app

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "backend" / "app" / "data"
EN = {e["id"]: e for e in json.loads((DATA / "diseases.json").read_text(encoding="utf-8"))["diseases"]}
UR = json.loads((DATA / "diseases_ur.json").read_text(encoding="utf-8"))
CROPS = json.loads((DATA / "crops.json").read_text(encoding="utf-8"))
TIPS = json.loads((DATA / "tips.json").read_text(encoding="utf-8"))
URDU = re.compile(r"[؀-ۿ]")
PRODUCT_WORDS = [
    "mancozeb",
    "chlorothalonil",
    "captan",
    "copper",
    "sulfur",
    "sulphur",
    "streptomycin",
    "carbendazim",
    "benlate",
    "bordeaux",
    "imidacloprid",
    "abamectin",
    "metalaxyl",
    "azoxystrobin",
    "tridemorph",
]
URDU_PRODUCT_WORDS = ["تانبا", "کاپر", "گندھک", "سلفر", "مینکوزیب", "بورڈو", "کاربینڈازم"]
DOSE = re.compile(r"\b\d+(\.\d+)?\s*(ml|g|kg|l|%|°c)\b|ملی لیٹر|گرام فی|فی لیٹر", re.IGNORECASE)


def test_urdu_layer_covers_every_disease_with_matching_lists():
    assert set(UR["diseases"]) == set(EN)
    assert UR["meta"]["needs_native_review"] is True
    pairs = [
        ("symptoms", "symptoms"),
        ("general_management", "prevention"),
        ("immediate_actions", "immediate_actions"),
        ("causes", "causes"),
        ("treatment_categories", "treatment_categories"),
        ("call_expert_when", "call_expert_when"),
    ]
    for class_id, en in EN.items():
        ur = UR["diseases"][class_id]
        assert URDU.search(ur["name"]) and URDU.search(ur["description"]), class_id
        for en_key, ur_key in pairs:
            assert len(ur[ur_key]) == len(en[en_key]), (class_id, en_key)
            assert all(URDU.search(item) for item in ur[ur_key]), (class_id, ur_key)


def _all_text(obj) -> str:
    if isinstance(obj, dict):
        return " ".join(_all_text(v) for k, v in obj.items() if k != "sources")
    if isinstance(obj, list):
        return " ".join(_all_text(v) for v in obj)
    return str(obj)


@pytest.mark.parametrize("name,payload", [("diseases_ur", UR), ("crops", CROPS), ("tips", TIPS)])
def test_no_product_names_or_doses(name, payload):
    text = _all_text(payload)
    lower = text.lower()
    assert not [w for w in PRODUCT_WORDS if w in lower], name
    assert not [w for w in URDU_PRODUCT_WORDS if w in text], name
    assert not DOSE.search(text), (name, DOSE.search(text))


def test_crops_cover_the_brief_and_are_sourced_and_bilingual():
    ids = {c["id"] for c in CROPS["crops"]}
    assert {"wheat", "rice", "cotton", "sugarcane", "tomato", "potato", "maize", "mango", "citrus"} <= ids
    for crop in CROPS["crops"]:
        assert crop["sources"] and all(u.startswith("https://") for u in crop["sources"]), crop["id"]
        assert crop["needs_review"] is True
        for field in ("name", "season", "summary"):
            assert crop[field]["en"] and URDU.search(crop[field]["ur"]), (crop["id"], field)
        assert len(crop["seasonal_care"]["en"]) == len(crop["seasonal_care"]["ur"])
        for disease in crop["diseases"]:
            assert len(disease["prevention"]["en"]) == len(disease["prevention"]["ur"]), (
                crop["id"],
                disease["name"],
            )
        for class_id in crop["scanner_classes"]:
            assert class_id in EN, class_id


def test_tips_are_bilingual_and_sourced():
    assert TIPS["meta"]["sources"] and len(TIPS["tips"]) >= 6
    for tip in TIPS["tips"]:
        assert tip["title"]["en"] and URDU.search(tip["title"]["ur"]) and URDU.search(tip["body"]["ur"])


def _client(tmp_path, model_dir):
    from fastapi.testclient import TestClient

    client = TestClient(
        create_app(
            Settings(
                model_dir=model_dir,
                data_dir=tmp_path / "d",
                inbox_dir=tmp_path / "i",
                frontend_dist=tmp_path / "nodist",
                rate_limit_per_minute=1000,
            )
        )
    )
    client.__enter__()
    return client


def test_disease_detail_and_prediction_carry_the_bilingual_report(tmp_path, tiny_model_dir):
    from tests.conftest import image_bytes

    client = _client(tmp_path, tiny_model_dir)
    detail = client.get("/api/diseases/Tomato___Late_blight").json()
    report = detail["report"]
    assert report["name"]["en"] == "Late blight" and URDU.search(report["name"]["ur"])
    assert report["crop"] == {"en": "Tomato", "ur": "ٹماٹر"}
    assert report["risk_level"] == "high"
    assert report["symptoms_early"]["en"] and report["symptoms_advanced"]["en"]
    assert len(report["prevention"]["ur"]) == len(report["prevention"]["en"])
    body = client.post(
        "/api/predict", files={"image": ("l.jpg", image_bytes(), "image/jpeg")}, data={"save": "false"}
    ).json()
    assert body["disease_info"]["report"]["id"] == body["class_id"]
    assert body["disease_info"]["report"]["name"]["ur"]
    client.__exit__(None, None, None)


def test_crop_and_tip_endpoints(tmp_path, tiny_model_dir):
    client = _client(tmp_path, tiny_model_dir)
    crops = client.get("/api/crops").json()["items"]
    wheat = next(c for c in crops if c["id"] == "wheat")
    assert wheat["scanner_supported"] is False and wheat["name"]["ur"] == "گندم"
    tomato = client.get("/api/crops/tomato").json()
    assert tomato["scanner_diseases"] and all(d["name"]["ur"] for d in tomato["scanner_diseases"])
    assert client.get("/api/crops/banana").status_code == 404
    assert len(client.get("/api/tips").json()["items"]) == len(TIPS["tips"])
    client.__exit__(None, None, None)
