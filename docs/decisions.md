# Decision log

Append-only. Each entry: date · decision · why · alternatives considered.

## 2026-11-09 · D1 Runtime inference uses ONNX Runtime, not PyTorch
**Why:** the app must install with one command on a weak Windows laptop. ONNX Runtime + NumPy + Pillow
is roughly 50 MB of wheels; PyTorch CPU is far larger. **Condition:** a parity test
(`ml/tests/test_export.py`) must show the ONNX outputs match PyTorch. **Alternative:** a PyTorch
runtime (heavier install, no accuracy gain).

## 2026-11-09 · D2 Every model ends in global-average-pool → linear; the ONNX model outputs CAMs
**Why:** with this head, Grad-CAM equals classic CAM exactly, so heatmaps can be computed without
autograd. The backend stays torch-free and the heatmap is exactly what the model used. A unit test
proves the equality. **Cost:** MobileNetV3's pretrained 960→1280 projection after pooling is
dropped (the head is re-initialized anyway).

## 2026-11-09 · D3 Pretrained weights come from timm's GitHub release assets
**Why:** in this build environment download.pytorch.org and huggingface.co are blocked, but GitHub
release assets are reachable. Weights are pinned by URL; timm filenames carry a SHA256 prefix,
which we verify. On Colab the same timm model names are used.

## 2026-11-09 · D4 Duplicate groups = official leaf map ∪ dihedral pHash ∪ embedding similarity
**Why:** PlantVillage contains several photos of each physical leaf. The repo's `leaf-map.json`
covers ~75% of images, so we use it as ground truth to score our detectors (precision/recall of
"same leaf" pairs), then apply the detectors to the uncovered classes. Groups are formed with
union-find; a group never crosses splits.

## 2026-11-09 · D5 Label space: all 38 PlantVillage classes, plus an optional crop hint
**Why:** comparable to published work, and it covers all 28 PlantDoc classes. A crop hint (the
farmer picks the crop) masks the other crops' classes at inference time.

## 2026-11-09 · D6 PlantDoc is a public field proxy; GB photos are field set #2 (PENDING)
**Why:** the GB photos cannot exist before spring, and the lab-to-field study should not wait.
PlantDoc is clearly labelled as web photos, never presented as GB data.

## 2026-11-09 · D7 Light dependencies for the app and frontend
Plain YAML configs (PyYAML + a small deep-merge), no Hydra. Rate limiting is an in-memory token
bucket (no extra package). i18n is a small React context + JSON files (no i18next). PWA uses a
hand-written service worker (no workbox). **Why:** fewer moving parts for a beginner-maintained
repo and a faster Windows install.

## 2026-11-09 · D8 Pins resolved with `uv pip compile --universal --python-version 3.11`
**Why:** one lock that is valid on Windows, macOS and Linux. On Colab the preinstalled
torch/torchvision are kept and their versions are logged in every run.

## 2026-11-09 · D9 ONNX export always forces eval mode and verifies parity (bug found and fixed)
**What happened:** with torch 2.15's TorchScript exporter, a freshly created wrapper module (training
mode) made the exporter fold BatchNorm with the *dummy input's* batch statistics. The exported model
then ignored most of the image (outputs nearly constant). The parity unit test caught it before any
model shipped; the first embedding pass for duplicate detection was discarded and recomputed.
**Fix:** `cropdoc.export.export_and_verify` sets eval mode, passes `training=EVAL`, and compares ONNX
Runtime with PyTorch on random inputs after every export, deleting the file on mismatch.

## 2026-11-09 · D10 Perceptual hashing alone cannot find same-leaf photos in PlantVillage (measured)
Scored against the official leaf map (pairs of mapped photos within a class), dihedral pHash links at
distance ≤ 4 find 0.16% of true same-leaf pairs at 8% precision (`results/data_audit/dedup_calibration.json`).
Same-leaf photos are re-shoots, not copies, and different leaves on the same plain background look
alike to a 64-bit hash. **Decision:** groups = official leaf map ∪ pretrained-embedding similarity
(threshold calibrated on the leaf map) ∪ pHash near-exact copies (≤ 2 bits, always linked).

## 2026-11-09 · D11 Final duplicate-linking rule (measured against the leaf map)
Generic ImageNet embeddings are also weak at finding same-leaf photos (cosine ≥ 0.96: precision 0.88,
recall 0.9%), because every photo of a class shares the same backdrop. Linking pHash distance ≤ 2
chained 1,240 near-identical Soybean photos into one group (over-merging). **Final rule:** official
leaf map ∪ embedding cosine ≥ 0.9625 (precision 0.92 vs the leaf map) ∪ identical pHash under
rotation/flip. Largest group: 200 photos (3.9% of Soybean healthy), which fits inside one 5% fold.

## 2026-11-09 · D12 App thresholds: energy at the 95%-TPR operating point (Milestone-2 calibration)
The M1 threshold (accept 99% of validation photos) let **19.9% of non-leaf photos** through as "confident"
(`results/ood/ood_summary.json`). Switched to the standard rule fixed in advance: accept 95% of
validation photos (`results/calibration/thresholds.json`). It is chosen on validation only; the OOD sets
were used only to report behaviour, never to tune it. Effect: non-leaf photos answered confidently 2.8%;
lab photos 94.0% (99.2% correct when confident); real-world PlantDoc photos 14.3% (42.5% correct when
confident), so the app now mostly says "not sure / unsupported" on field photos. That is honest given the
21% real-world accuracy. The "not sure" confidence threshold is unchanged (99% selective accuracy on validation).

## 2026-11-09 · D13 Leakage inflation is small for PlantVillage; the lab→field gap is the main problem (measured)
Naive vs group-aware split: +0.24 accuracy points for the frozen-feature head (95% CI −0.12 to +0.64),
+2.0 for 1-NN (a memorizing model), +0.8 to +1.1 for the classical and MLP baselines
(`results/leakage/leakage_summary.json`). The lab→PlantDoc drop is 77 points. The README leads with the
field gap and reports leakage honestly as a smaller, model-dependent effect. Fine-tuned CNNs (Colab block C)
may memorize more: PENDING.

## 2026-11-09 · D14 Windows: detect a broken ONNX Runtime at start-up and guide the fix
A Windows user saw "DLL load failed while importing onnxruntime_pybind11_state", and the app wrongly
suggested retraining the model. The usual cause is a missing or outdated Microsoft Visual C++
Redistributable (x64). Now: (1) the backend separates "engine cannot start" from "model missing" and
shows the fix with the official download link; (2) `scripts/ensure_deps.py` (run by start.bat) test-imports
ONNX Runtime on every start and, only with the user's consent, installs the runtime with winget or opens
the download link; (3) README has a Troubleshooting section. Not reproducible on Linux here; covered by a
unit test that simulates the Windows import error.

## 2026-11-25 · D15 Live Scan runs the model on the server, about two frames per second, with a 2-of-3 vote
**What:** a Live Scan page sends the part of the camera image inside an on-screen box to a new endpoint,
`POST /api/predict/live` (no saving, small transparent heatmap). The page shows a disease as found only when **2 of the
last 3 frames** are `confident` about the same class, and keeps it until the window holds no confident frame for it.
**Why:** single frames can be blurry or caught mid-movement, so answers would flicker; a short vote keeps the screen
steady while reacting within about a second. Server-side inference reuses the exact same ONNX model, temperature
and thresholds as the photo scanner (a test checks that both endpoints agree on the same image), so the safety rules
stay in one place. **Alternatives:** running the model in the browser with onnxruntime-web (works offline on the
phone, but duplicates preprocessing, calibration and OOD logic in TypeScript and adds a ~12 MB download plus a large
WASM runtime; possible later); sending every frame (wasteful on phones and Wi-Fi). Live frames get their own rate
limit bucket (240/min/IP) so they cannot starve photo scans. **Verified:** Playwright with a fake webcam showing a
PlantVillage test photo (desktop landscape and phone portrait frames) locks on the right class with the real model.

## 2026-11-25 · D16 Phone mode = HTTPS on the local network with a self-signed certificate
Browsers expose the camera only on secure origins (`https://` or `localhost`), so a phone opening
`http://192.168.x.x:8000` cannot use Live Scan. `run.py --phone` (`start-phone.bat`, `./start.sh --phone`, `make phone`)
creates a certificate once in `data/app/certs` (EC P-256, valid 825 days, covering the LAN IPs; recreated when the
Wi-Fi address changes), serves on `0.0.0.0:8443`, prints the phone address and exposes it at `GET /api/network` so the
laptop shows a QR code. The phone shows a one-time "not private" warning. Adds the `cryptography` package (wheels for
Windows, macOS, Linux). **Alternatives:** mkcert (needs a CA installed on every phone: too hard for farmers), a tunnel
service (sends photos through a third party), cloud deployment (documented in `docs/deploy.md` for use without a laptop).
When the page is opened over plain HTTP anyway, it explains why and offers "Take a photo" (works everywhere).

## 2026-11-26 · D17 Vercel support: same app as a serverless function, with honest limits
**What happened:** the owner deployed the repository to Vercel and it did not run: Vercel runs serverless functions,
and the repository had no entry point or dependency list it could use (only `backend/requirements.txt` and a start
script). **Changes:** a root `index.py` exposes the FastAPI app; `pyproject.toml` declares the runtime libraries
(pinned like `backend/requirements.txt`, a test keeps them equal; no PyTorch; `[tool.vercel] entrypoint`);
`vercel.json` builds the web app; `.vercelignore` leaves out training code and datasets. On Vercel (`VERCEL` env var)
data goes to `/tmp/cropdoc`, the rate limiter uses the visitor IP from the proxy headers, the model also loads on the
first request if the host skips the start-up event, and `/api/health` reports `temporary_storage: true` so the UI
warns that saved scans are temporary and shared. Because requests are capped at 4.5 MB, the browser now shrinks
photos above 3.5 MB to at most 2048 px JPEG before upload (useful on mobile data everywhere). The Live Scan full
report is shown from the server's answer in a dialog instead of re-reading it from history, so it works when saved
data lives on another copy of the function. **Verified here:** a rehearsal with the upload set from `.vercelignore`,
Python 3.12 (Vercel's default), dependencies installed from `pyproject.toml` (177 MB, limit 500 MB), a read-only
project folder and an unprivileged user: pages, assets, live scan, saving, history and research data all respond.
**Not verified here:** a real Vercel build (vercel.com is not reachable from this environment).
**Alternatives:** frontend on Vercel + API elsewhere (two deployments and CORS for a beginner); recommending only
Render / Hugging Face Spaces (kept as the first choice in `docs/deploy.md` because history persists there).

## 2026-11-26 · D18 Never crash at start-up; detect serverless hosts from several signals
**What happened:** the Vercel deployment answered `500 FUNCTION_INVOCATION_FAILED`. Reproduced here by running the app
through Vercel's own open-source Python handler (`vercel-runtime` 0.26.0, the package Vercel's builder installs) on a
read-only copy as an unprivileged user: when the `VERCEL` variable is not present at runtime, the app tried to create
`data/app` inside the read-only project folder, the start-up step raised `PermissionError`, and the function failed.
**Fix:** (1) serverless detection uses several signals (`VERCEL*`, Vercel's handler variables `__VC_HANDLER_*`,
AWS Lambda variables); (2) `with_writable_storage` test-writes the data folder and falls back to the temp folder
(marked temporary) instead of crashing; (3) a failed start-up no longer stops the server: `/api/health` returns the
reason and other endpoints answer 503 with it; (4) if the app cannot even be imported, `index.py` serves a plain
page with the error type and location (standard library only). **Verified:** with and without `VERCEL`, Vercel's
handler serves `/api/health` (model loaded), `/`, `/live`, a live frame, a saved scan and the history.

## 2026-11-26 · D19 The project requires Python 3.11 (the Vercel build failed on a 3.10 claim)
**What happened:** GitHub shows Vercel's verdict for each commit: the v1.1.1 and v1.1.2 deployments **failed at build
time**, so the older v1.1.0 deployment (no Vercel setup) stayed live and kept answering 500. Vercel installs Python
libraries with `uv lock` on `pyproject.toml`, which resolves *every* Python version the project claims. It claimed
`>=3.10`, but the pinned numpy 2.4 needs 3.11+, so `uv lock` stopped with "No solution found" (reproduced here).
**Fix:** `requires-python = ">=3.11"`; `start.sh`, `start.bat` and `scripts/ensure_deps.py` also ask for 3.11+
(with 3.10 the pinned libraries could never install). A test keeps these in line. `uv lock --no-build` and
`uv sync --no-build --python 3.12` now succeed, as on Vercel.

## 2026-11-26 · D20 vercel.json pins the framework, install and output settings
v1.1.3 still failed to build on Vercel. Reading Vercel's builder code (`@vercel/python`, `@vercel/frameworks`): our
build command runs only when the project's framework is a Python preset; with the dashboard preset "Other" (likely,
because the project was created before the repository looked like a FastAPI app) the build is treated as static and
expects an output folder; and a leftover dashboard Install Command replaces the Python install. `vercel.json` now
sets `"framework": "fastapi"`, `"installCommand": ""` (empty = Vercel installs `pyproject.toml` with uv),
`"outputDirectory": "public"` (the FastAPI preset's static folder; `public/robots.txt` keeps it present).
The real Vercel build log was not available here; the result is read from the commit status on GitHub.

## 2026-11-26 · D21 The real Vercel failure: Root Directory was `backend`
The owner's build log showed `Creating virtual environment at "/vercel/path0/backend/..."`, `Installing required
dependencies from backend/requirements.txt` and `cd: frontend: No such file or directory`: the Vercel project's Root
Directory is `backend`, so Vercel never saw the repository root (model, web app, `pyproject.toml`, `index.py`). That
also explains the earlier 500: Vercel ran `backend/app/main.py` directly and it crashed writing to the read-only
folder (fixed in D18 anyway). **Fix:** set Root Directory to the repository root in the Vercel dashboard (only the
owner can change it). The build command now stops with a plain message naming this setting if `frontend/` is missing.

## 2026-11-26 · D22 Field-robust model v2: pre-registered training, calibration and promotion rules
**Why:** the owner's new brief asks to improve real-world accuracy instead of hiding it; v1 is ~21% correct on
real-world photos. **Data:** PlantDoc gets its own group-aware split (embedding cosine >= 0.95 ∪ identical dihedral
pHash; StratifiedGroupKFold 20: 60/15/25 → 1,545 / 387 / 646 photos, `ml/splits/plantdoc_group_aware.csv.gz`).
**Training (`python -m cropdoc.field_model`):** weighted linear head (lab train + field train), then fine-tune the
last 4 blocks for <= 6 epochs on <= 200 lab photos/class with background randomization (procedural backgrounds only;
the ImageNet photos stay unseen because they are the non-leaf test set) + field train photos x3 with strong
augmentation; best epoch by mean(lab val, field val) macro-F1. **Calibration (validation only):** temperature and the
"not sure" threshold on domain-balanced validation (lab = field weight), lowest confidence with >= 95% accuracy on
kept photos; "unsupported" energy threshold accepts >= 95% of validation photos in each domain.
**Promotion (replaces the lab-only rule 5 for this comparison):** v2 replaces v1 only if field-test macro-F1 improves
by >= 5 points, lab-test macro-F1 drops by <= 1 point, and <= 5% of non-leaf photos are answered "confident".
These rules were written into the code before any test result was seen; a 1-epoch smoke run (152 lab photos)
then checked the pipeline end to end and nothing was changed after it.

## 2026-11-28 · D23 Model v2 is not deployed: it missed the pre-registered lab rule
**Result** (`results/field_model/comparison.json`, one run, 43 minutes on 4 CPU cores, evaluated once):
real-world test photos (646 PlantDoc photos, own group-aware split) accuracy 23.4% → 68.1% (+44.7 points, 95% CI
+40.1 to +49.2), macro-F1 0.227 → 0.678, calibration error 0.479 → 0.074; lab test photos (8,145) accuracy
98.3% → 97.3% (−1.0 points, 95% CI −1.4 to −0.7), macro-F1 0.981 → 0.967; non-leaf photos answered "confident"
2.8% → 3.7%. **D22 rules:** real-world gain ≥ 5 points ✓ (45.1), lab drop ≤ 1 point ✗ (1.37), non-leaf ≤ 5% ✓.
**Decision:** v2 is not promoted; `models/active/` still holds v1 (CLAUDE.md rule 5 is not met either: v2 does not
beat v1 on the group-aware lab test). The rule is kept as written: relaxing it after seeing the test result would make
the pre-registration meaningless. **Open for the owner:** (a) deploy v2 anyway as an explicit, logged owner decision
(`python -m cropdoc.field_model` re-creates and installs it in about 45 minutes once the check is changed), or (b) a new
pre-registered run that also protects lab accuracy (for example more lab photos per class per epoch), judged by the
same rules; it would reuse the same test photos a second time, which must be reported. The comparison is shown on the
Field Intelligence page and in README/MODEL_CARD (generated from `results/field_model/summary.json`).

## 2026-11-28 · D24 Photo check before analysis: too dark, too bright or blurry → "please take another photo"
**What:** brightness = mean grey level (0–255); sharpness = variance of the Laplacian (edge strength) after resizing
to 384 px. **Thresholds (validation only):** each check flags at most 1% of domain-balanced validation photos
(1,504 lab + 387 real-world): min brightness 65.6, max brightness 221.0, min sharpness 70.5
(`models/active/quality.json`, `results/quality/quality_summary.json`). **Measured:** artificially darkened /
brightened / blurred validation photos are flagged 100% / 99.3% / 100% of the time; false alarms on test photos are
2.1% (lab) and 5.3% (real-world). **Behaviour:** status `retake_photo`; the disease is never shown and the scan is not
saved; Live Scan shows the same advice per frame. The threshold code (`ml/src/cropdoc/quality.py`) and the server
check (`backend/app/services/quality.py`) are kept identical by a parity test. **Not covered:** a sharp photo of the
wrong thing (the "unsupported" warning handles that).

## 2026-11-28 · D25 Bilingual Plant Analysis Report; generic treatment categories allowed, products and doses never
The owner's brief asks for English and Urdu on the same screen and for treatment categories and "when to call an
expert". `diseases.json` gains `risk_level` + `risk_reason` (the disease's general loss potential from the cited
sources, not a measurement of the photographed plant), `causes`, `immediate_actions`, `treatment_categories` and
`call_expert_when`; `diseases_ur.json` holds the Urdu (machine-written, `needs_native_review`). The API returns both
languages in `disease_info.report`; the result screen shows them side by side (`lang`/`dir` per text, self-hosted
Noto Nastaliq Urdu font). **Content rule (CLAUDE.md rule 3 updated):** generic categories such as "a fungicide labelled
for this disease" are allowed only in `treatment_categories` and always send the farmer to the extension officer and
the label; product or active-ingredient names (for example "copper-type" was removed), doses, spray intervals and
application methods are never written. Tests check every English and Urdu field.

## 2026-11-28 · D26 Agriculture assistant: knowledge-base retrieval first, Claude optional, never invented answers
**Retrieval:** BM25 keyword search over the disease, crop and tip entries in English, Urdu script and common Roman Urdu
words (small word map); healthy entries count less. **With `ANTHROPIC_API_KEY`:** Claude (default `claude-opus-5-5`,
effort `medium`, server-side fallback) writes a short answer only from the retrieved entries, in the language of the
question, with the same safety rules, and asks a follow-up question when the crop or symptoms are unclear. **Without a
key, on an API error or a refusal:** the best passages are returned in the farmer's language (`mode: knowledge_base`),
kept short for a phone. Roman Urdu questions get Urdu-script answers there (Roman Urdu writers usually read Urdu script
better than English; in AI mode Claude mirrors the exact script). A question that names a disease ("late blight")
ranks that disease above the general crop page.
**Privacy:** the page says questions go to Anthropic in AI mode; CropDoc stores no chats; 20 requests per minute per IP.
Tests use a fake client (no network). **Why not a fully generative bot:** the brief forbids unsupported claims, and a
grounded answer can always show its sources.

## 2026-11-28 · D27 Weather from Open-Meteo through the server; farmer dashboard
**Weather:** Open-Meteo (free, no key, CC BY 4.0 attribution shown) fetched by the server, so the browser contacts no
third party; coordinates rounded to 0.1° (about 10 km); 30-minute cache; `available: false` when offline (everything
else still works); off with `CROPDOC_WEATHER=off`. Advisories are rules of thumb on the forecast (rain likely, frost
≤ 2 °C, heat ≥ 40 °C), not disease predictions. **Dashboard:** the home page is now a farmer dashboard (big Live Scan /
photo buttons, tiles for history, crops, assistant, tips and language, weather and two tips); the research summary
stays below it. **Crops and tips:** 9 crops and 9 tips in English and Urdu with sources (`crops.json`, `tips.json`,
`needs_review: true`).

## 2026-11-28 · D28 The zip keeps `public/` for Vercel; temp-folder tests work on Windows
**What happened:** the downloaded zip had no `public/` folder, because `scripts/package.py` did not list it, but
`vercel.json` sets `"outputDirectory": "public"` (D20). A Vercel project made from that zip could stop with "no output
directory". The GitHub repository already has `public/robots.txt`, so deployments from GitHub were not affected.
**Fix:** `package.py` now includes `public`. The two serverless tests
compared against a hard-coded `/tmp`, while the app uses the system temp folder (`/tmp` on Vercel, `%TEMP%` on
Windows). They now compare against `tempfile.gettempdir()`, so the same check passes on the owner's Windows laptop.
**Verified here (Windows, Python 3.11):** backend tests pass, frontend tests, type check and lint pass, `npm ci && npm
run build` works, and the root `index.py` with `VERCEL=1` reports `model_loaded: true` and serves the web app.
**Not verified here:** a real Vercel build. ML tests need PyTorch, which is not installed in this environment.
