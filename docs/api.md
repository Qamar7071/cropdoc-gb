# CropDoc GB API

Base URL when running locally: `http://127.0.0.1:8000`. Interactive OpenAPI docs: `/docs` (Swagger UI) and
`/openapi.json`. All responses are JSON unless noted. No accounts; nothing personal is stored.

## Health and model

### `GET /api/health`
```json
{ "status": "ok", "app_version": "1.1.2", "model_loaded": true, "model_version": "quick-mbv3l-2026-11-09",
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
                    "needs_review": true },
  "gradcam_png": "<base64 PNG: heatmap over the model's 224×224 view>",
  "heatmap_png": "<base64 PNG: heatmap only>", "model_view_jpeg": "<base64 JPEG: the crop the model saw>",
  "scores": { "max_softmax": 0.97, "energy": -9.1 },
  "thresholds": { "min_confidence": 0.64, "max_energy": -3.93, "provisional": true, "source": "…" },
  "crop_hint": null, "district": "Skardu", "model_version": "quick-mbv3l-2026-11-09",
  "disclaimer": "General guidance only, not a diagnosis. Please consult an agriculture expert." }
```
The numbers above are placeholders that show the shape only. Real values come from the model.

`status`:
- `confident`: the calibrated top-class probability is ≥ `min_confidence` and the energy is ≤ `max_energy`.
- `low_confidence`: the top-class probability is below `min_confidence`. Show "Not sure, please consult an agriculture expert".
- `not_a_leaf_or_unsupported_crop`: the energy score is above `max_energy`. The photo looks unlike anything in training (a non-leaf, or an unsupported crop such as apricot).

Errors:
- 413: the file or the image dimensions are too large.
- 415: not a valid JPG/PNG.
- 422: unknown crop_hint or district.
- 429: rate limit (default 30 per minute per IP on `/api/predict` and `/api/contribute`; live frames have their own bucket, below).
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
- `GET /api/diseases?crop=&q=` returns `{items:[{id, crop, disease, category, description, needs_review, image}], crops}`.
- `GET /api/diseases/{id}` returns the full entry: `symptoms`, `spread`, `most_affected_part`, `general_management` (cultural practices only), `sources` (URLs), `needs_review`, `images`.

## Research
`GET /api/field-intelligence` returns `{sections: {key: {title, source, status: "ready"|"pending", data | pending_reason}}, ready, total}`.
Each section is one file in `results/`:

| key | file |
|---|---|
| `leakage` | `results/leakage/leakage_summary.json` |
| `background` | `results/background/background_summary.json` |
| `plantdoc_gap` | `results/shift/plantdoc_gap.json` |
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
