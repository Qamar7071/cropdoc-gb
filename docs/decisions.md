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
