# CropDoc GB: plan

A working plant-disease scanner (FastAPI + React) for farmers in Gilgit-Baltistan (GB),
plus an honest study of why lab-trained models fail on field photos.
Milestone 1 ships a usable zip (v0.1). Milestone 2 deepens the research and ships v1.0.

## 0. Facts checked before planning (measured, not assumed)

| Fact | Consequence |
|---|---|
| PlantVillage GitHub repo: 54,305 colour images, 38 classes (152 to 5,507 per class), plus a background-removed twin of each image; license CC BY-SA 3.0 | free leaf masks for background randomization and the "is the model looking at the leaf?" metric |
| The repo ships `leaf-map.json`: 40,490 of 54,305 images mapped to 7,946 physical leaves (most leaves have 4 photos, max 33); several classes (all Corn, Apple black rot, Grape healthy, ...) have no mapping | a random split leaks photos of the same leaf into train and test; the map is ground truth for scoring our duplicate detector |
| PlantDoc (CC BY 4.0): ~2.6k real-world leaf photos, 28 classes, each name-matched to a PlantVillage class | a public field-like test set we can use now, while the GB photos are pending |
| Build machine: 4 CPU, 15 GB RAM, no GPU; PyPI, npm, GitHub (git + release assets) reachable; download.pytorch.org and huggingface.co blocked | quick model trained here on CPU with timm's GitHub-hosted ImageNet weights; the full sweep runs on Colab |

## 1. Architecture

```
            ┌──────────────────── one process: uvicorn ─────────────────────┐
 browser ──►│ FastAPI  /api/*  ── services: inference (ONNX Runtime) · gradcam │
 (React SPA)│                     ood · history (SQLite) · diseases · stats    │
            │ static:  frontend/dist (SPA) · /examples · /library images        │
            └──────────────┬──────────────────────────────┬────────────────────┘
                           │ reads                         │ reads
                 models/active/                      results/*.json
          model.onnx · classes.json             (field intelligence, metrics)
          model_card.json · calibration.json              ▲
                           ▲                               │ writes
                           │ export                        │
                 ml/src/cropdoc  (data → split → train → evaluate → calibrate → shift → explain)
                           ▲
              data/ (gitignored): PlantVillage, PlantDoc, field_test (GB, PENDING)
```

Key design choices (see `docs/decisions.md`):
- **No PyTorch at runtime.** The app needs only ONNX Runtime + NumPy + Pillow + FastAPI, so `start.bat` installs quickly on a weak Windows laptop. PyTorch is used only for training and export, and a parity test proves ONNX ≡ PyTorch.
- **Grad-CAM without autograd.** Every model ends in global-average-pool → linear, so Grad-CAM equals classic CAM exactly. The ONNX graph outputs both the logits and the per-class CAMs; a unit test proves the equivalence.
- **Crop hint.** When the farmer picks a crop, only that crop's classes compete (masked softmax). This reduces errors at zero training cost, and the gain is measured in Milestone 2.
- **Honest numbers only.** `/api/health`, About and Field Intelligence read `models/active/model_card.json` and `results/*.json`. A missing file means `PENDING`; the app never shows a sample number.

## 2. API contract (full details in `docs/api.md` and at `/docs`)

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | `{status, model_loaded, model_version, classes, metrics}` from model_card.json |
| POST | `/api/predict` | multipart `image` (+ `crop_hint`, `district`, `save`=true). Returns `{scan_id, status, top3[{class_id, crop, disease, probability}], crop, disease, confidence, gradcam_png (base64), disease_id, thresholds}`. `status` ∈ `confident`, `low_confidence`, `not_a_leaf_or_unsupported_crop` |
| GET | `/api/scans` | `?q=&disease=&district=&date_from=&date_to=&page=&page_size=` → paginated list |
| GET / DELETE | `/api/scans/{id}` | one scan (with result) / delete |
| GET | `/api/scans/{id}/image`, `/thumbnail`, `/gradcam` | stored images (EXIF-free) |
| POST | `/api/scans/{id}/feedback` | `{correct: bool, correct_class_id?}` stored for future few-shot adaptation |
| GET | `/api/stats` | counts by disease, by ISO week, by district, from saved scans only (zeros when empty) |
| GET | `/api/diseases`, `/api/diseases/{id}` | library content (`needs_review` flags kept) |
| GET | `/api/field-intelligence` | lab-vs-field gap, calibration, few-shot curve, leakage study; each section `ready` or `pending` |
| POST | `/api/contribute` | opt-in field photo + class label + consent → `data/inbox/` |

Upload rules: JPG/PNG only (checked by decoding with Pillow, not by extension), ≤ 5 MB, decompression-bomb guard, EXIF/GPS stripped, simple per-IP rate limit, CORS origins configurable, no accounts, no personal data.

## 3. Milestones and gates

| Milestone | Deliverable | Gate |
|---|---|---|
| M1.1 Foundations | scaffold, pinned envs, Makefile, ruff, pytest, CI, seeding, logging | `make lint` + `make test` green |
| M1.2 Data + quick model | download, group-aware split (leaf-map ∪ pHash ∪ embeddings), quick model in `models/active/` with REAL test metrics | split tests (no group crosses splits); ONNX parity test |
| M1.3 Backend | all endpoints + security + tests | pytest green (uploads, schema, CRUD, empty stats, no-model state) |
| M1.4 Frontend | 7 pages, EN/UR + RTL, PWA, camera, feedback, print report | vitest + Playwright e2e; screenshots at 1440/768/390 in `results/ui/` compared to `design/` |
| M1.5 Package v0.1 | `dist/cropdoc-gb-complete.zip`, start.bat/start.sh | unzip into empty dir → start script → `/api/health` + one real prediction |
| M2 Research → v1.0 | leakage study, baselines, CNN matrix (Colab), calibration/OOD, field shift, few-shot, ONNX polish, docs | every displayed number traced to a `results/` file; model swapped only if better on group-aware test |

## 4. Experiment matrix

**Quick model (M1, CPU here):** MobileNetV3-Large (ImageNet). First a linear head on frozen features; then a brief fine-tune of the last blocks with standard augmentation. Then temperature scaling and the "not sure" threshold, both chosen on validation. Real test metrics go to `model_card.json`.

**CPU-feasible research (M2, here, real numbers):**
- leakage: the same frozen-feature model under the naive vs the group-aware split, plus a 1-NN leakage probe
- baselines: LR/RF on colour/texture features, MLP on 32 px pixels
- background: border-pixel variance, and a background-only classifier
- calibration: ECE and reliability diagrams
- OOD: AUROC for held-out diseases and non-leaf images
- PlantDoc field proxy: the lab→field gap, the crop-hint gain, and a few-shot curve (k = 5/10/20)
- CAM mass outside the leaf

**Colab sweep (M2, GPU, PENDING until run):** estimates only, replaced by measured epoch times.

| Block | Design | Runs | Est. T4 GPU-h |
|---|---|---:|---:|
| A imbalance | ResNet18 · standard aug · {CE, weighted CE, balanced sampler} × 3 seeds | 9 | 3.0 |
| B model × aug | {SmallCNN, ResNet18, MobileNetV3} × {none, standard, strong, bg-rand} × 3 seeds (one cell reused from A) | 33 | 15.5 |
| C leakage | 3 models · standard aug · naive split × 3 seeds | 9 | 3.5 |
| E open-set | best config with 4 diseases held out × 3 seeds | 3 | 1.3 |
| F few-shot | k ∈ {5, 10, 20} × 2 source models × 3 seeds (PlantDoc now, GB later) | 18 short | 0.6 |
| Total core | + misc 0.8 h | 72 | ≈25 (≈31 with buffer) |

Estimate assumptions: T4 + AMP, 224 px, ~38k training images, data loading limited to ~500 img/s (standard aug) or ~350 img/s (strong) by Colab's 2 vCPUs, ≤12 epochs pretrained / ≤20 SmallCNN.

Statistics: mean ± std over 3 seeds; paired bootstrap 95% CIs for the pre-registered comparisons (`docs/preregistration.md`).

## 5. Top risks

1. **GB field photos arrive late** (November: little foliage until spring), need expert-confirmed labels, and will cover few classes. → PlantDoc proxy + BG-swap now; GB pipeline, loader and `docs/field_collection_guide.md` ready; GB results marked PENDING.
2. **The quick model is CPU-trained** (frozen features + brief fine-tune), so it is weaker on field photos than a full fine-tune. → It is clearly labelled "quick model"; the Colab sweep replaces it only if it beats it on the group-aware test split.
3. **The one-command Windows start can fail** (no Python, PATH, proxy). → Runtime deps are pure wheels (no torch); start.bat checks for Python ≥ 3.10 and prints fix steps; the fresh-unzip test runs on Linux here; Windows is untested here (flagged).
4. **The leakage groups may be wrong** (pHash misses re-shot leaves; embeddings can over-merge). → Thresholds are scored against the official leaf map, group sizes audited, and leakage reported at several thresholds.
5. **Unsafe or wrong content** (disease advice, machine-written Urdu). → Cultural practices only, never chemicals or doses, real source URLs, `needs_review` flags, Urdu file marked "needs native review", and a disclaimer on every result.
