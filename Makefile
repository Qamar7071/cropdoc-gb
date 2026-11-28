# CropDoc GB developer commands (Linux / macOS / Colab). Windows users: start.bat runs the app.
PY  ?= .venv/bin/python
UV  ?= uv
NPM ?= npm
export PYTHONPATH := $(CURDIR)/ml/src:$(CURDIR)/backend

HAS_WEB := $(wildcard frontend/package.json)

.PHONY: help setup data split train api phone web web-build test test-py test-web lint format e2e package \
        baseline leakage background sweep sweep-status promote eval calibrate ood shift fewshot explain export \
        report research smoke train-field quality

help: ## list targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-12s %s\n", $$1, $$2}'

# ----------------------------------------------------------------------------- setup + data
setup: ## create .venv (Python 3.11) with pinned deps, install frontend deps
	$(UV) venv .venv --python 3.11
	$(UV) pip install --python $(PY) -r backend/requirements.txt -r ml/requirements.txt -r requirements-dev.txt
	@if [ -n "$(HAS_WEB)" ]; then cd frontend && $(NPM) ci; fi

data: ## download PlantVillage (+ masks) and PlantDoc into data/raw
	$(PY) scripts/download_data.py --plantdoc

split: ## manifest, duplicate groups, group-aware + naive splits (ml/splits)
	$(PY) -m cropdoc.data.build_splits

train: ## quick CPU model -> models/active (real metrics in model_card.json)
	$(PY) scripts/train_quick.py

train-field: ## model v2 (lab + real-world photos, ~45 min CPU); installs only if the D22 rules pass
	$(PY) -m cropdoc.field_model

quality: ## photo-check limits (too dark / too bright / blurry) from validation photos
	$(PY) -m cropdoc.research.quality

# ----------------------------------------------------------------------------- app
api: ## run the app (API + built frontend) at http://127.0.0.1:8000
	$(PY) backend/run.py --no-browser

phone: ## run over HTTPS on your Wi-Fi so a phone can use the live camera (prints the address)
	$(PY) backend/run.py --phone --no-browser

web: ## frontend dev server with hot reload (proxies /api to :8000)
	cd frontend && $(NPM) run dev

web-build: ## build the frontend into frontend/dist
	cd frontend && $(NPM) run build

# ----------------------------------------------------------------------------- quality
test: test-py test-web ## all unit tests

test-py:
	$(PY) -m pytest

test-web:
	@if [ -n "$(HAS_WEB)" ]; then cd frontend && $(NPM) run test; else echo "frontend not scaffolded yet"; fi

lint: ## ruff + frontend type-check/lint
	$(PY) -m ruff check .
	$(PY) -m ruff format --check .
	@if [ -n "$(HAS_WEB)" ]; then cd frontend && $(NPM) run lint; fi

format: ## auto-fix Python lint + format
	$(PY) -m ruff check --fix .
	$(PY) -m ruff format .

e2e: ## Playwright end-to-end tests + screenshots -> results/ui
	cd frontend && $(NPM) run e2e

package: ## build frontend, run tests, create dist/cropdoc-gb-complete.zip
	$(PY) scripts/package.py

# ----------------------------------------------------------------------------- research (Milestone 2)
baseline: ## classical + MLP + 1-NN baselines on both splits (CPU; part of the leakage study)
	$(PY) -m cropdoc.research.leakage

leakage: ## naive vs group-aware split with frozen features (CPU)
	$(PY) -m cropdoc.research.leakage

background: ## background uniformity + background-only probe (CPU)
	$(PY) -m cropdoc.research.background

sweep: ## model x augmentation x split matrix (GPU / Colab); SWEEP_ARGS="--block B"
	$(PY) -m cropdoc.sweep $(SWEEP_ARGS)

sweep-status: ## done / missing runs per block
	$(PY) -m cropdoc.sweep --status

promote: ## swap a sweep run into models/active only if better: make promote RUN=<run_id>
	$(PY) -m cropdoc.promote --run $(RUN)

eval: ## tidy results table + bootstrap CIs from saved logits
	$(PY) -m cropdoc.evaluate

calibrate: ## ECE, reliability diagram, temperature scaling, thresholds wired into the app
	$(PY) -m cropdoc.research.calibrate
	$(PY) -m cropdoc.research.thresholds

ood: ## OOD AUROC (held-out diseases, non-leaf images)
	$(PY) -m cropdoc.research.ood_eval

shift: ## lab vs PlantDoc / GB field evaluation
	$(PY) -m cropdoc.research.shift_eval

fewshot: ## few-shot adaptation curve (k = 5, 10, 20)
	$(PY) -m cropdoc.research.fewshot

explain: ## Grad-CAM galleries + CAM mass outside the leaf
	$(PY) -m cropdoc.research.explain_eval

export: ## ONNX export + parity check + CPU latency benchmark
	$(PY) -m cropdoc.export

research: leakage background shift calibrate ood fewshot explain export ## every CPU experiment

report: ## refresh docs tables/figures from results/
	$(PY) -m cropdoc.report

smoke: ## tiny end-to-end training run on synthetic data (CPU, seconds)
	$(PY) -m cropdoc.train --config ml/configs/smoke.yaml
