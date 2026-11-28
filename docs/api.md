# CropDoc GB API

Base URL when running locally: `http://127.0.0.1:8000`. Interactive OpenAPI docs: `/docs` (Swagger UI) and
`/openapi.json`. All responses are JSON unless noted. No accounts; nothing personal is stored.

## Health and model

### `GET /api/health`
```json
{ "status": "ok", "app_version": "1.2.0", "model_loaded": true, "model_version": "quick-mbv3l-2026-11-09",
  "reason": null, "num_classes": 38, "thresholds_provisional": true, "temporary_storage": false,
  "metrics": { "test_accuracy": 0.983, "test_macro_f1": 0.981, "test_n": 8145, "source": "results/quick_model/metrics.json" } }
```
`metrics` is copied verbatim from `models/active/model_card.json` (real measured values). When no model is
installed: `model_loaded: false` and `reason` explains how to train one. `temporary_storage` is `true` on serverless
hosts (Vercel), where saved scans can disappear; the UI then shows a notice on My Scoutings and Dashboard.

### `GET /api/model`
Class list (`id`, `crop`, `disease`, `healthy`), supported `crops`, the 10 GB `districts`, the full
`model_card` and `calibration` blocks.

## Prediction

### `POST /api/predict` (multipart/form-data)
| field | type | notes |
|---|---|---|
| `image` | file | JPG or PNG, ≤ 5 MB. Checked by decoding with Pillow (the extension is ignored). |
| `crop_hint` | string, optional | one of `/api/model` `crops`; only that crop's classes compete |
| `district` | string, optional | one of Skardu, Gilgit, Hunza, Nagar, Ghizer, Astore, Diamer, Ghanche, Shigar, Kharmang |
| `save` | bool, default `true` | save the scan (EXIF-free image, thumbnail, Grad-CAM, result) to history |

Response (abridged):
```json
{ "scan_id": "4f0c…", "saved": true, "status": "confident",
  "class_id": "Potato___Early_blight", "crop": "Potato", "disease": "Early blight", "healthy": false,
  "confidence": 0.97,
  "top3": [ { "class_id": "Potato___Early_blight", "crop": "Potato", "disease": "Early blight", "probability": 0.97 } ],
  "disease_info": { "id": "Potato___Early_blight", "description": "…", "category": "fungal",
                    "recommendations": ["…", "Consult your local agriculture extension officer for approved products and doses."],
                    "needs_review": true,
                    "report": { "name": { "en": "Early blight", "ur": "…" }, "crop": { "en": "Potato", "ur": "آلو" },
                                "risk_level": "medium", "risk_reason": { "en": "…", "ur": "…" },
                                "symptoms_early": { "en": ["…"], "ur": ["…"] }, "symptoms_advanced": { … },
                                "causes": { … }, "immediate_actions": { … }, "prevention": { … },
                                "treatment_categories": { … }, "call_expert_when": { … },
                                "extension_fallback": { … }, "sources": ["https://…"], "needs_review": true,
                                "urdu_needs_review": true } },
  "gradcam_png": "<base64 PNG: heatmap over the model's 224×224 view>",
  "heatmap_png": "<base64 PNG: heatmap only>", "model_view_jpeg": "<base64 JPEG: the crop the model saw>",
  "scores": { "max_softmax": 0.97, "energy": -9.1 },
  "thresholds": { "min_confidence": 0.64, "max_energy": -3.93, "provisional": true, "source": "…" },
  "quality": { "checked": true, "ok": true, "issues": [], "brightness": 120.5, "sharpness": 410.2 },
  "crop_hint": null, "district": "Skardu", "model_version": "quick-mbv3l-2026-11-09",
  "disclaimer": "General guidance only, not a diagnosis. Please consult an agriculture expert." }
```
The numbers above are placeholders that show the shape only. Real values come from the model.

`status`:
- `confident`: the calibrated top-class probability is ≥ `min_confidence` and the energy is ≤ `max_energy`.
- `low_confidence`: the top-class probability is below `min_confidence`. Show "Not sure, please consult an agriculture expert".
- `not_a_leaf_or_unsupported_crop`: the energy score is above `max_energy`. The photo looks unlike anything in training (a non-leaf, or an unsupported crop such as apricot).
- `retake_photo`: the photo is too dark, too bright or blurry (`quality.issues`: `too_dark`, `too_bright`, `blurry`).
  The app shows "please take another photo" with advice and **never shows the disease**; the scan is **not saved**.
  The other fields are still filled (the model always runs) but must not be shown as a result.

`quality` comes from `models/active/quality.json`: brightness is the mean grey level (0–255) and sharpness the
variance of the Laplacian (edge strength) after resizing to 384 px. The limits are the 1st/99th percentiles of
real validation photos (lab and field weighted equally), measured by `python -m cropdoc.research.quality`
(`results/quality/quality_summary.json`). Without that file the check is skipped (`checked: false`).

`disease_info.report` is the bilingual knowledge for the result screen. It comes from `backend/app/data/diseases.json`
(English, cited sources) and `diseases_ur.json` (Urdu, machine-written: `urdu_needs_review: true`), **never from the
photo**: the model only picks the class. `risk_level` is the disease's general loss potential from the sources, not a
measurement of this plant. `treatment_categories` are generic (for example "a fungicide recommended by your extension
officer"); no product names or doses anywhere (enforced by tests in English and Urdu).

Errors:
- 413: the file or the image dimensions are too large.
- 415: not a valid JPG/PNG.
- 422: unknown crop_hint or district.
- 429: rate limit (default 30 per minute per IP on `/api/predict` and `/api/contribute`; live frames and the assistant have their own buckets, below).
- 503: no model is loaded. A prediction is never invented.

### `POST /api/predict/live` (multipart/form-data)
One frame from the live camera. Same model, temperature, thresholds and `status` rules as `/api/predict`, but
**nothing is saved** and no full-size images are returned, so a phone can call it about twice a second.

| field | type | notes |
|---|---|---|
| `image` | file | JPG or PNG, ≤ 5 MB; the app sends the scan-box area as a ~384 px square JPEG |
| `crop_hint` | string, optional | as above |

Response (abridged; numbers show the shape only):
```json
{ "status": "confident", "class_id": "Potato___Early_blight", "crop": "Potato", "disease": "Early blight",
  "healthy": false, "confidence": 0.97, "top3": [ … ], "disease_info": { … },
  "heatmap_png": "<base64 RGBA PNG, 112×112: Grad-CAM with transparency, drawn over the camera view>",
  "quality": { "checked": true, "ok": true, "issues": [] },
  "crop_hint": null, "model_version": "quick-mbv3l-2026-11-09", "inference_ms": 12.3,
  "disclaimer": "General guidance only, not a diagnosis. Please consult an agriculture expert." }
```
`inference_ms` is the server time measured for this frame. The app decides what to show from several frames
(see `frontend/src/lib/live.ts`: a disease is shown as found only when 2 of the last 3 frames agree confidently).
Rate limit: `CROPDOC_LIVE_RATE_LIMIT_PER_MINUTE` (default 240 per IP), separate from the photo scanner's limit.

### `GET /api/network`
`{ "phone_mode": true, "urls": ["https://192.168.1.20:8443"] }` when started with `run.py --phone`
(`start-phone.bat`, `./start.sh --phone`), otherwise `{ "phone_mode": false, "urls": [] }`. The Live Scan page turns the
first URL into a QR code for the phone.

## History

| Method | Path | Notes |
|---|---|---|
| GET | `/api/scans` | `q` (search disease/crop), `disease` (class id), `crop`, `district`, `date_from`, `date_to` (YYYY-MM-DD), `page`, `page_size` (≤ 100). Returns `{items, total, page, page_size}` newest first |
| GET | `/api/scans/{id}` | one scan + `top3`, `image_url`, `gradcam_url`, `feedback` |
| GET | `/api/scans/{id}/image` · `/thumbnail` · `/gradcam` | JPEG / JPEG / PNG bytes |
| DELETE | `/api/scans/{id}` | 204; feedback is deleted too |
| POST | `/api/scans/{id}/feedback` | JSON `{ "correct": true }` or `{ "correct": false, "correct_class_id": "Potato___Late_blight" }` |

## Dashboard
`GET /api/stats` returns `total_scans`, `healthy_scans`, `diseased_scans`, `by_disease`, `by_week` (ISO weeks), `by_district`, and
`feedback {total, correct, incorrect}`. These are computed **only from saved scans**. An empty database returns zeros
and empty lists.

## Disease library
- `GET /api/diseases?crop=&q=` returns `{items:[{id, crop, crop_ur, disease, name_ur, category, risk_level, description, needs_review, image}], crops}`.
- `GET /api/diseases/{id}` returns the full entry: `symptoms`, `spread`, `most_affected_part`, `general_management` (cultural practices only), `sources` (URLs), `needs_review`, `images`, and `report` (the bilingual block described under `/api/predict`, used by the detail page's overview, early/advanced symptoms and treatment guide).

## Crop information and farming tips
Bilingual (English + Urdu) reference content for 9 important Pakistani crops, from cited sources
(`backend/app/data/crops.json`, `tips.json`; `needs_review: true` until an expert checks them).
- `GET /api/crops` returns `{items:[{id, name{en,ur}, season, summary, scanner_supported, diseases}], meta}`.
  Crops: wheat, rice, cotton, sugarcane, tomato, potato, maize, mango, citrus.
- `GET /api/crops/{id}` returns the crop with `diseases` (name, symptoms, prevention), `seasonal_care`, `sources`,
  and `scanner_diseases` (the classes the scanner knows for that crop; empty for crops the model does not cover). 404 if unknown.
- `GET /api/tips` returns 9 general good-practice tips (scouting, clean seed, rotation, soil testing, water, field hygiene,
  IPM, safe handling, records) with FAO sources.

## AI agriculture assistant
- `GET /api/assistant/status` returns `{ai_available, model, privacy{en,ur}}`.
- `POST /api/assistant/chat` (JSON):
  ```json
  { "messages": [ { "role": "user", "content": "گندم کی فصل کو بیماری سے کیسے بچاؤں؟" } ], "class_id": null }
  ```
  `messages`: 1–12 turns, each ≤ 2,000 characters, the last one from the user. `class_id` (optional, from a scan
  result) puts that disease's knowledge first. Response:
  ```json
  { "reply": "…", "language": "ur", "mode": "ai", "model": "claude-opus-5-5", "notice": null,
    "related": [ { "kind": "crop", "id": "wheat", "title": { "en": "Wheat", "ur": "گندم" } } ],
    "sources": ["https://…"], "disclaimer": "General guidance only, not a diagnosis. Please consult an agriculture expert." }
  ```
  **How it answers:** the server first finds the most relevant entries in the CropDoc knowledge base (diseases, crops,
  tips; keyword search that understands English, Urdu script and common Roman Urdu words). With an AI key
  (`ANTHROPIC_API_KEY`), Claude writes a short answer **only from those entries**, in the language of the question,
  with the same safety rules (no product names or doses; "consult your extension officer"), and asks a follow-up
  question when the crop or symptoms are unclear. Without a key, or if the AI service fails or declines, `mode` is
  `knowledge_base` and the reply is the best-matching verified passages in the farmer's language
  (`notice`: `ai_not_configured` or `ai_unavailable`). It never invents an answer.
  Model: `CROPDOC_ASSISTANT_MODEL` (default `claude-opus-5-5`), effort `CROPDOC_ASSISTANT_EFFORT` (default `medium`).
  Rate limit: `CROPDOC_ASSISTANT_RATE_LIMIT_PER_MINUTE` (default 20 per IP). Chats are not stored by CropDoc.

## Weather
`GET /api/weather?district=Gilgit` or `?lat=35.9&lon=74.3` returns
`{available, place, current{temperature, humidity, wind_kmh, summary{en,ur}}, daily[3]{date, temp_min, temp_max,
precipitation_probability, precipitation_mm, summary}, advisories[{en,ur}], advisory_note, attribution}`.
Data: [Open-Meteo](https://open-meteo.com) (free, no key, CC BY 4.0), fetched by this server and cached for
30 minutes. Coordinates are rounded to 0.1° (about 10 km) before they leave the server. Advisories are simple
rules on the forecast (rain likely, frost risk, heat), not disease predictions. Offline or blocked:
`{available: false, reason: "unreachable"}`; switched off with `CROPDOC_WEATHER=off`: `reason: "disabled"`.

## Research
`GET /api/field-intelligence` returns `{sections: {key: {title, source, status: "ready"|"pending", data | pending_reason}}, ready, total}`.
Each section is one file in `results/`:

| key | file |
|---|---|
| `leakage` | `results/leakage/leakage_summary.json` |
| `background` | `results/background/background_summary.json` |
| `plantdoc_gap` | `results/shift/plantdoc_gap.json` |
| `field_model` | `results/field_model/summary.json` (model v1 vs v2 and the deployment rules) |
| `field_gap` | `results/shift/field_gap.json` (GB photos, PENDING until collected) |
| `calibration` | `results/calibration/calibration_summary.json` |
| `ood` | `results/ood/ood_summary.json` |
| `fewshot_plantdoc` | `results/shift/fewshot_plantdoc.json` |
| `fewshot_field` | `results/shift/fewshot_field.json` |
| `cam_focus` | `results/explain/cam_outside_leaf.json` |
| `sweep` | `results/sweep/summary.json` (Colab, PENDING until run) |

## Contribute a field photo
`POST /api/contribute` (multipart): `image`, `label` (class id or free text), `consent` (must be `true`), and an optional
`district`. The photo is saved EXIF-free to `data/inbox/<label>/<id>.jpg`, with a JSON note that its label is unverified.
