"""API tests: health, predict (valid and invalid uploads), history CRUD, feedback, stats, library."""

from __future__ import annotations

import base64
import io
import json

from PIL import Image

from tests.conftest import image_bytes


def upload(client, data: bytes, name: str = "leaf.jpg", content_type: str = "image/jpeg", **form):
    return client.post("/api/predict", files={"image": (name, data, content_type)}, data=form)


# ---------------------------------------------------------------- health / model-not-loaded
def test_health_without_model_reports_not_loaded(make_client):
    body = make_client().get("/api/health").json()
    assert body["model_loaded"] is False
    assert "train_quick.py" in body["reason"]


def test_predict_without_model_returns_503_not_a_fake_result(make_client):
    response = upload(make_client(), image_bytes())
    assert response.status_code == 503
    assert "Model not loaded" in response.json()["detail"]


def test_health_with_model(make_client, tiny_model_dir):
    body = make_client(tiny_model_dir).get("/api/health").json()
    assert body["model_loaded"] is True
    assert body["model_version"] == "test-fixture"
    assert body["num_classes"] == 3


def test_model_info_lists_classes_crops_districts(make_client, tiny_model_dir):
    body = make_client(tiny_model_dir).get("/api/model").json()
    assert body["crops"] == ["Potato", "Tomato"]
    assert "Skardu" in body["districts"] and len(body["districts"]) == 10


# ---------------------------------------------------------------- predict: valid
def test_predict_schema_and_saved_to_history(make_client, tiny_model_dir):
    client = make_client(tiny_model_dir)
    response = upload(client, image_bytes(), district="Gilgit")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] in {"confident", "low_confidence", "not_a_leaf_or_unsupported_crop"}
    assert body["saved"] is True and body["scan_id"]
    assert 1 <= len(body["top3"]) <= 3
    probs = [p["probability"] for p in body["top3"]]
    assert probs == sorted(probs, reverse=True) and abs(sum(probs) - 1.0) < 1e-5  # 3 classes → sums to 1
    assert body["confidence"] == probs[0]
    overlay = Image.open(io.BytesIO(base64.b64decode(body["gradcam_png"])))
    assert overlay.format == "PNG" and overlay.size == (224, 224)
    assert body["disease_info"]["recommendations"], "recommendations come from the disease library"
    assert "not a diagnosis" in body["disclaimer"]
    listing = client.get("/api/scans").json()
    assert listing["total"] == 1 and listing["items"][0]["district"] == "Gilgit"


def test_predict_save_false_does_not_store(make_client, tiny_model_dir):
    client = make_client(tiny_model_dir)
    body = upload(client, image_bytes(), save="false").json()
    assert body["saved"] is False and body["scan_id"] is None
    assert client.get("/api/scans").json()["total"] == 0


def test_predict_png_with_transparency(make_client, tiny_model_dir):
    response = upload(make_client(tiny_model_dir), image_bytes("PNG", alpha=True), "leaf.png", "image/png")
    assert response.status_code == 200, response.text


def test_crop_hint_restricts_classes(make_client, tiny_model_dir):
    body = upload(make_client(tiny_model_dir), image_bytes(), crop_hint="tomato").json()
    assert body["crop_hint"] == "Tomato"
    assert {p["crop"] for p in body["top3"]} == {"Tomato"}
    assert abs(body["confidence"] - 1.0) < 1e-6  # only one tomato class in the fixture


def test_unknown_crop_hint_and_district_rejected(make_client, tiny_model_dir):
    client = make_client(tiny_model_dir)
    assert upload(client, image_bytes(), crop_hint="Apricot").status_code == 422
    assert upload(client, image_bytes(), district="Lahore").status_code == 422


# ---------------------------------------------------------------- predict: invalid uploads
def test_oversize_file_rejected(make_client, tiny_model_dir):
    big = b"\xff\xd8\xff" + b"\0" * (5 * 1024 * 1024)
    assert upload(make_client(tiny_model_dir), big).status_code == 413


def test_corrupted_image_rejected(make_client, tiny_model_dir):
    truncated = image_bytes()[:200]
    assert upload(make_client(tiny_model_dir), truncated).status_code == 415


def test_non_image_with_jpg_name_rejected(make_client, tiny_model_dir):
    response = upload(make_client(tiny_model_dir), b"this is not an image at all", "leaf.jpg")
    assert response.status_code == 415


def test_gif_rejected_even_though_it_is_an_image(make_client, tiny_model_dir):
    assert upload(make_client(tiny_model_dir), image_bytes("GIF"), "leaf.gif", "image/gif").status_code == 415


def test_empty_file_rejected(make_client, tiny_model_dir):
    assert upload(make_client(tiny_model_dir), b"").status_code in (400, 422)


def test_decompression_bomb_rejected(make_client, tiny_model_dir):
    client = make_client(tiny_model_dir, max_image_pixels=1_000_000)
    bomb = image_bytes("PNG", size=(2000, 2000), color=(0, 0, 0))  # 4 Mpx but a tiny file
    assert upload(client, bomb, "bomb.png", "image/png").status_code == 413


def test_exif_and_gps_are_stripped(make_client, tiny_model_dir):
    exif = Image.Exif()
    exif[0x010F] = "PhoneMaker"  # Make
    exif[0x8825] = {1: "N", 2: (35.0, 55.0, 0.0)}  # GPS IFD (latitude)
    client = make_client(tiny_model_dir)
    scan_id = upload(client, image_bytes(exif=exif.tobytes())).json()["scan_id"]
    stored = Image.open(io.BytesIO(client.get(f"/api/scans/{scan_id}/image").content))
    assert len(stored.getexif()) == 0
    assert b"PhoneMaker" not in client.get(f"/api/scans/{scan_id}/image").content


def test_rate_limit(make_client, tiny_model_dir):
    client = make_client(tiny_model_dir, rate_limit_per_minute=2)
    codes = [upload(client, image_bytes(), save="false").status_code for _ in range(3)]
    assert codes == [200, 200, 429]


# ---------------------------------------------------------------- history + feedback
def test_history_crud_search_filter(make_client, tiny_model_dir):
    client = make_client(tiny_model_dir)
    first = upload(client, image_bytes(), crop_hint="Tomato", district="Hunza").json()
    upload(client, image_bytes(), crop_hint="Potato", district="Skardu")
    assert client.get("/api/scans").json()["total"] == 2
    assert client.get("/api/scans", params={"q": "late"}).json()["total"] == 1
    assert client.get("/api/scans", params={"district": "Skardu"}).json()["total"] == 1
    assert client.get("/api/scans", params={"disease": "Tomato___Late_blight"}).json()["total"] == 1
    detail = client.get(f"/api/scans/{first['scan_id']}").json()
    assert detail["crop"] == "Tomato" and detail["image_url"].endswith("/image")
    assert client.get(detail["thumbnail_url"]).headers["content-type"] == "image/jpeg"
    assert client.get(detail["gradcam_url"]).headers["content-type"] == "image/png"
    assert client.delete(f"/api/scans/{first['scan_id']}").status_code == 204
    assert client.get(f"/api/scans/{first['scan_id']}").status_code == 404
    assert client.delete(f"/api/scans/{first['scan_id']}").status_code == 404


def test_pagination(make_client, tiny_model_dir):
    client = make_client(tiny_model_dir)
    for _ in range(3):
        upload(client, image_bytes())
    page = client.get("/api/scans", params={"page": 2, "page_size": 2}).json()
    assert page["total"] == 3 and len(page["items"]) == 1


def test_feedback_flow(make_client, tiny_model_dir):
    client = make_client(tiny_model_dir)
    scan_id = upload(client, image_bytes()).json()["scan_id"]
    url = f"/api/scans/{scan_id}/feedback"
    assert client.post(url, json={"correct": True}).json()["correct"] is True
    assert client.post(url, json={"correct": False}).status_code == 422
    assert client.post(url, json={"correct": False, "correct_class_id": "Nope"}).status_code == 422
    body = client.post(url, json={"correct": False, "correct_class_id": "Potato___healthy"}).json()
    assert body["correct_class_id"] == "Potato___healthy"
    assert client.get(f"/api/scans/{scan_id}").json()["feedback"]["correct"] is False
    assert client.post("/api/scans/doesnotexist/feedback", json={"correct": True}).status_code == 404


# ---------------------------------------------------------------- stats
def test_stats_empty_database_returns_zeros(make_client):
    body = make_client().get("/api/stats").json()
    assert body["total_scans"] == 0 and body["healthy_scans"] == 0 and body["diseased_scans"] == 0
    assert body["by_disease"] == [] and body["by_week"] == [] and body["by_district"] == []
    assert body["feedback"] == {"total": 0, "correct": 0, "incorrect": 0}


def test_stats_counts_real_scans(make_client, tiny_model_dir):
    client = make_client(tiny_model_dir)
    upload(client, image_bytes(), crop_hint="Tomato", district="Hunza")
    upload(client, image_bytes(), crop_hint="Tomato")
    body = client.get("/api/stats").json()
    assert body["total_scans"] == 2
    assert body["by_disease"][0] == {
        "key": "Tomato___Late_blight",
        "label": "Late blight (Tomato)",
        "count": 2,
    }
    assert {d["key"]: d["count"] for d in body["by_district"]} == {"Hunza": 1, "Unspecified": 1}
    assert sum(w["count"] for w in body["by_week"]) == 2


# ---------------------------------------------------------------- library, research, contribute
def test_disease_library(make_client):
    client = make_client()
    body = client.get("/api/diseases", params={"crop": "Potato"}).json()
    assert [i["id"] for i in body["items"]] == ["Potato___Early_blight", "Potato___healthy"]
    assert client.get("/api/diseases", params={"q": "late"}).json()["items"][0]["crop"] == "Tomato"
    detail = client.get("/api/diseases/Potato___Early_blight").json()
    assert detail["needs_review"] is True and detail["images"] == []
    assert client.get("/api/diseases/Nope").status_code == 404


def test_field_intelligence_pending_then_ready(make_client, tmp_path):
    results = tmp_path / "results"
    client = make_client(results_dir=results)
    body = client.get("/api/field-intelligence").json()
    assert body["ready"] == 0 and body["sections"]["field_gap"]["status"] == "pending"
    (results / "shift").mkdir(parents=True)
    (results / "shift" / "plantdoc_gap.json").write_text(json.dumps({"lab": {"accuracy": 0.5}}))
    body = make_client(results_dir=results).get("/api/field-intelligence").json()
    assert body["sections"]["plantdoc_gap"]["status"] == "ready"
    assert body["sections"]["plantdoc_gap"]["source"] == "results/shift/plantdoc_gap.json"


def test_contribute_requires_consent_and_saves_to_inbox(make_client, tmp_path):
    client = make_client()
    files = {"image": ("f.jpg", image_bytes(), "image/jpeg")}
    assert (
        client.post(
            "/api/contribute", files=files, data={"label": "Potato late blight", "consent": "false"}
        ).status_code
        == 400
    )
    files = {"image": ("f.jpg", image_bytes(), "image/jpeg")}
    body = client.post(
        "/api/contribute", files=files, data={"label": "Potato late blight", "consent": "true"}
    ).json()
    saved = list((tmp_path / "inbox").rglob(f"{body['id']}.*"))
    assert sorted(p.suffix for p in saved) == [".jpg", ".json"]


def test_spa_fallback_and_api_404(make_client, tmp_path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html>CropDoc</html>")
    client = make_client(frontend_dist=dist)
    assert "CropDoc" in client.get("/history/abc").text
    assert client.get("/api/nope").status_code == 404
