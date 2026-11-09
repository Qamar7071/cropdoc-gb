# Model card: CropDoc GB plant-disease classifier

## Model details
- **Task:** classify one leaf photo into 38 PlantVillage classes (14 crops; diseases and healthy leaves).
- **Architecture:** MobileNetV3-Large pretrained on ImageNet (timm weights), then global-average-pool and one
  linear layer. Because the head is linear after pooling, the exported model can output class activation maps
  that equal Grad-CAM (unit-tested).
- **Runtime:** ONNX Runtime on CPU (no PyTorch needed). The ONNX/PyTorch parity is checked at export.
- **Version and metrics:** see the table below (generated from `models/active/model_card.json`).

## Intended use
- General guidance for farmers, students and extension workers in Gilgit-Baltistan, Pakistan: to recognise a
  likely leaf disease early and to decide when to consult an expert.
- **Not** for diagnosis, regulatory decisions, pesticide choices, or crops outside the 38 classes.

## Training data
PlantVillage colour photos (lab conditions, single leaf, plain background), with the group-aware split:
<!-- BEGIN:data_facts -->
- 54,305 PlantVillage photos in 38 classes (152–5507 per class).
- 41,479 photos belong to groups of the same physical leaf (official leaf map + near-duplicate detection); 20,671 groups in total.
- A naive random split puts a same-leaf sibling of **74.8%** of test photos into training (6,092 of 8,146).
- Group-aware split used for every reported number: 38,010 train / 8,150 val / 8,145 test, 0 groups crossing splits (SHA256 `c45b4f872b70…`).

_Source: `results/data_audit/`, `ml/splits/manifest.json`._
<!-- END:data_facts -->

## Evaluation (lab photos, group-aware test split)
<!-- BEGIN:quick_metrics -->
| Metric | Value |
|---|---|
| Test accuracy (group-aware split, lab photos) | 98.31% |
| Test macro-F1 | 0.981 |
| Test photos | 8,145 |
| Validation accuracy / macro-F1 | 98.37% / 0.980 |
| Calibration error (ECE) before → after temperature | 0.0032 → 0.0030 |
| Temperature (fitted on validation) | 1.033 |
| 'Confident' threshold / test coverage / accuracy when confident | 0.64 / 98.8% / 98.9% |
| Training time (CPU only) | 15.6 min |
| Model | MobileNetV3-Large (ImageNet-pretrained, timm) + global-average-pool + linear head · `quick-mbv3l-2026-11-09` |

_Source: `results/quick_model/metrics.json`, `models/active/model_card.json`._
<!-- END:quick_metrics -->

## Lab → field (research status)
<!-- BEGIN:research_status -->
| Study | Status | Result file |
|---|---|---|
| Leakage: naive vs group-aware split | ready | `results/leakage/leakage_summary.json` |
| Background uniformity / background-only probe | ready | `results/background/background_summary.json` |
| Lab → real-world photos (PlantDoc) | ready | `results/shift/plantdoc_gap.json` |
| Lab → Gilgit-Baltistan field photos | **PENDING** | `results/shift/field_gap.json` |
| Calibration (ECE, reliability) | ready | `results/calibration/calibration_summary.json` |
| OOD detection (AUROC) | ready | `results/ood/ood_summary.json` |
| Few-shot adaptation (PlantDoc) | ready | `results/shift/fewshot_plantdoc.json` |
| Few-shot adaptation (GB photos) | **PENDING** | `results/shift/fewshot_field.json` |
| Grad-CAM mass outside the leaf | ready | `results/explain/cam_outside_leaf.json` |
| Model × augmentation sweep (3 seeds, Colab) | **PENDING** | `results/sweep/summary.json` |
<!-- END:research_status -->

## Real-world performance (PlantDoc web photos, same classes)
<!-- BEGIN:headline_gap -->
| Same 28 classes | Lab photos (PlantVillage test) | Real-world photos (PlantDoc) | Real-world + crop hint |
|---|---|---|---|
| Accuracy | 98.1% | 20.8% | 50.7% |
| Macro-F1 | 0.982 | 0.198 | 0.510 |
| Calibration error (ECE) | 0.003 | 0.501 | — |
| App says 'confident' | 93.2% | 14.3% | — |
| …and is right when confident | 99.0% | 42.5% | — |
| Photos | 5,774 | 2,578 | 2,578 |

Accuracy drop lab → real-world: **77.2 (95% CI 75.6 to 78.9) points**. PlantDoc photos identical to a PlantVillage photo: 0.

_Source: `results/shift/plantdoc_gap.json` (deployed model; PlantDoc = public web photos, not GB photos)._
<!-- END:headline_gap -->

## Unfamiliar inputs and the app's thresholds
<!-- BEGIN:ood_table -->
| Unfamiliar input | AUROC (max-softmax) | AUROC (energy) | Photos |
|---|---|---|---|
| Unseen diseases (4 held out) | 0.808 | 0.770 | 638 |
| Non-leaf photos (everyday objects) | 0.976 | 0.991 | 985 |
| Real-world leaf photos (PlantDoc) vs lab photos | 0.956 | 0.967 | 2,578 |

With the thresholds now used by the app (chosen on validation data only): lab photos are answered confidently 94.0% of the time; real-world photos 14.3%; non-leaf photos 2.8%. The rest get "not sure" or "unsupported".

_Source: `results/ood/ood_summary.json`, `results/calibration/thresholds.json`._
<!-- END:ood_table -->

## Shortcut learning (background reliance)
<!-- BEGIN:shortcut -->
- A classifier that sees **only the background** (leaf pixels removed) reaches 59.8% accuracy; one that sees only an 8-pixel border reaches 61.4% (chance: 2.6%, majority class: 3.2%).
- Deployed model, leaf painted grey (background only): 24.3% accuracy; background removed (leaf on black): 82.8%; original photos: 98.4%.
- Grad-CAM: 28.5% of the heat falls outside the leaf, while the background covers 40.8% of the image (median ratio 0.67; below 1 = focused on the leaf).

_Source: `results/background/background_summary.json`, `results/explain/cam_outside_leaf.json`._
<!-- END:shortcut -->

## Limitations and known failure modes
- **Domain shift:** field photos (soil, hands, several leaves, shadows, phone cameras) differ from the lab photos;
  accuracy and calibration collapse on real-world photos (tables above). GB field photos: PENDING.
- **Shortcut risk:** PlantVillage backgrounds are uniform per capture session, and the model partly relies on them
  (tables above). Background randomization is tested in the Colab sweep (PENDING).
- **Unsupported inputs:** non-leaf photos and crops outside the 38 classes (e.g. apricot) usually trigger the
  "unsupported" status, but not always (see the OOD table); unseen diseases of known crops are much harder to flag.
- **Look-alike diseases** (e.g. early blight vs target spot vs bacterial spot on tomato) are hard even for experts.
- **Label space:** PlantVillage class names do not cover every local disease or variety.

## Ethical considerations
- The model never recommends chemicals or doses. Guidance is limited to cultural practices with cited sources,
  awaiting expert review.
- Every result screen shows: "General guidance only, not a diagnosis. Please consult an agriculture expert."
- Privacy: inference runs locally; uploaded photos are stripped of EXIF/GPS data; there are no accounts.

## Reproducibility
- Split files with SHA256 hashes: `ml/splits/`. Training: `scripts/train_quick.py` (seed 42, CPU).
- Full sweep (3 seeds per configuration): `ml/notebooks/colab_run.ipynb`.
