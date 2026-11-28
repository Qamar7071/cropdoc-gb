# CLAUDE.md: rules for working on CropDoc GB

## What this repo is
A full-stack plant-disease scanner for farmers in Gilgit-Baltistan (FastAPI backend +
React frontend + ONNX model) plus a research layer studying the lab-to-field gap.
Plan: `docs/PLAN.md`. Decisions: `docs/decisions.md` (append, never rewrite history).

## Non-negotiable rules
1. **Never fabricate or estimate a number, plot, chart value, statistic, testimonial or
   result.** Every number in the UI or docs comes from a file in `results/`,
   `models/active/model_card.json`, or real saved scans. If something cannot be run
   here (full Colab training, GB field photos), write the code and mark the output
   `PENDING` (the API returns `"status": "pending"`, the UI shows a PENDING state).
2. **Never ship placeholder predictions.** If no model is loaded, the API reports
   `model_loaded: false`, `/api/predict` returns HTTP 503 with instructions, and the
   UI shows "Model not loaded".
3. **Disease content safety:** cultural practices, plus generic treatment categories only in
   `treatment_categories` (e.g. "a fungicide labelled for this disease", always with "ask your
   extension officer / follow the label"). Never write product or active-ingredient names, doses,
   spray intervals or application methods. Use "Consult your local agriculture extension officer
   for approved products and doses." Anything not checked against a cited source keeps
   `needs_review: true`. Every result screen keeps the disclaimer. Tests enforce this (EN + UR).
4. **No leakage:** the group-aware split (`ml/splits/`) is the only split used for
   reported metrics. Model selection, temperature and thresholds use validation data
   only; test and field sets are evaluation-only.
5. Swap a new model into `models/active/` **only** if it beats the current one on the
   group-aware test split (macro-F1), and regenerate `model_card.json` from result files.
6. Urdu strings are machine-written: keep `frontend/src/i18n/ur.json` and
   `backend/app/data/diseases_ur.json` marked "needs native review".
7. Use design references in `design/` as inspiration only; original branding (CropDoc GB),
   no third-party logos, names or icons.

## Working mode
- Work in milestones with gates (see PLAN.md). After each gate: run tests, then summarize
  in ≤ 5 lines (built / verified / risks / next).
- Ask the user only when blocked by a costly-to-redo choice; otherwise decide and log it
  in `docs/decisions.md`.
- Explain intuition first in comments and docs; formulas only when needed. The owner is
  new to deep learning.

## Layout
```
backend/app/      FastAPI app (main.py, api/, services/, db.py, schemas.py,
                  data/diseases.json + diseases_ur.json, crops.json, tips.json)
backend/tests/    pytest (uses a tiny generated ONNX model; no real model needed)
frontend/         React + Vite + TS + Tailwind (src/pages, src/components, src/lib, src/i18n)
ml/src/cropdoc/   training/research package (data, models, train, evaluate, calibration,
                  shift, explain, export); ml/configs; ml/notebooks/colab_run.ipynb
ml/splits/        committed split CSVs + manifest (SHA256)
models/active/    model.onnx, classes.json, model_card.json, calibration.json
results/          every metric/plot as json/csv/png (read by API and docs)
data/             gitignored datasets; data/field_test/<class>/ for GB photos
scripts/          download_data.py, train_quick.py, package.py
```

## Commands
```
make setup      # venv (.venv, Python 3.11) + all pinned deps + frontend npm ci
make data       # download PlantVillage (+ masks) and PlantDoc
make split      # manifest, duplicate groups, group-aware + naive splits
make train      # quick CPU model -> models/active (scripts/train_quick.py)
make train-field  # model v2 (lab + real-world photos); installs only if the D22 rules pass
make quality    # photo-check limits (dark/bright/blurry) from validation photos -> models/active/quality.json
make api        # run backend on http://localhost:8000 (serves built frontend)
make phone      # HTTPS on the Wi-Fi (self-signed) so phones can use Live Scan; prints the address
make web        # Vite dev server (proxy /api -> :8000)
make test       # backend + ml pytest, frontend vitest
make lint       # ruff (python) + tsc/eslint (frontend)
make e2e        # Playwright e2e + screenshots -> results/ui/
make package    # build frontend, run tests, create dist/cropdoc-gb-complete.zip
make research   # every CPU experiment → results/ (leakage, background, shift, calibrate, ood, fewshot, explain, export)
make sweep SWEEP_ARGS="--block B" / make sweep-status / make eval   # GPU matrix (Colab notebook)
make promote RUN=<run_id>   # swap a sweep run into models/active only if better (group-aware test macro-F1)
make report     # refresh README/MODEL_CARD number blocks from results/ (CI: report --check)
```
Python: always via `.venv/bin/python` (Windows: `.venv\Scripts\python`).
Pins: edit `*.in`, then re-run `uv pip compile <file>.in --universal --python-version 3.11 -o <file>.txt`.

## Conventions
- Python 3.11, type hints, docstrings, small modules; ruff (line length 110).
- Seeds everywhere via `cropdoc.utils.seed_everything` (python, numpy, torch, cudnn flags).
- Backend runtime must not import torch. Training code must not import backend code.
- No data, checkpoints or node_modules in git. `models/active/model.onnx` (small) is committed.
- Frontend: TypeScript strict, Tailwind v4 theme tokens in `src/index.css` (`@theme`), all user-facing
  strings via `t()` from `src/i18n` (English + Urdu), RTL handled by `dir` on `<html>`.
