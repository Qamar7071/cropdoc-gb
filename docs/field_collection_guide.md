# Field photo collection guide (Gilgit-Baltistan)

These photos become the **GB field test set**: the most important result of the project. Until they exist,
the app and the docs show "PENDING" for every GB number. Quality and honest labels matter more than quantity.

## 1. When and what to photograph
- **Season:** leaves with active symptoms, roughly late spring to early autumn (about April–September,
  depending on valley and altitude). Plan two or three visits per crop, since symptoms change over weeks.
- **Crops and classes:** only the model's classes can be tested (folder names in `data/field_test/`, e.g.
  `Potato___Late_blight`, `Potato___Early_blight`, `Potato___healthy`, `Apple___Apple_scab`,
  `Cherry_(including_sour)___Powdery_mildew`, `Tomato___Early_blight`, `Corn_(maize)___Common_rust_`, …).
  Focus on the crops common in your district (potato, apple, cherry, tomato, maize, grape, peach).
- **Unsupported crops are useful too:** 30–50 photos of apricot, walnut or mulberry leaves, and of
  non-leaves (soil, hands, fruit), go in `data/field_test_unsupported/`. They test the "unsupported" warning.

## 2. How many
| Goal | Photos |
|---|---|
| Minimum per class to report a number | 30 photos from at least 10 different plants |
| Good per class | 60–100 photos from 20+ plants, 2+ fields, 2+ days |
| Few-shot study (k = 5, 10, 20) | an **extra** 20+ photos per class, from different plants than the test photos |
| Healthy leaves | as many as for each disease of that crop (the model must not cry wolf) |

## 3. How to photograph (like a farmer would, but consistently)
- **One leaf fills most of the frame** (the app crops the centre). Hold the phone 15–30 cm away.
- **Angles:** mostly from above; for 1 photo in 4, also photograph the underside (some diseases show there).
- **Light:** daylight; avoid harsh noon shadows when possible, but include a few cloudy and some shaded
  photos. No flash.
- **Backgrounds:** keep the leaf **on the plant** with its natural background (soil, other leaves, sky).
  Do not pick the leaf and put it on paper: that recreates the lab conditions we are trying to move away from.
- **Phones:** if possible use two different phones; write the phone model in your notes.
- Sharp focus on the lesions; delete blurry shots.

## 4. File naming (prevents leakage between photos of the same leaf)
`<district>_<plantID>_<leafID>_<yyyymmdd>_<n>.jpg`, for example `Skardu_P012_L03_20270614_2.jpg`.
- `plantID` is unique per plant within a field visit (P001, P002, …); `leafID` is unique per leaf on that plant.
- Several photos of the same leaf share `plantID` + `leafID`. The code keeps such photos together, so a leaf is
  never in the few-shot training pool and the test set at the same time (`ml/src/cropdoc/research/common.py`).
- Put each photo in its class folder: `data/field_test/<class_id>/…`.

## 5. Labels: get them checked
- Labels must be confirmed by an **agriculture extension officer or plant pathologist**. Keep a CSV
  `data/field_test/labels.csv` with: `file, class_id, confirmed_by, confidence (sure/likely), notes`.
- If the expert is unsure, put the photo in `data/field_test_uncertain/` (not used for scoring).
- Never relabel photos after seeing what the model predicted.

## 6. Privacy and consent
- Ask the farmer's permission before photographing their field. Do not photograph faces or house numbers.
- The app strips GPS/EXIF from uploads. For the test set, keep only the district (no coordinates).

## 7. After collecting
```bash
make shift      # lab vs GB field: accuracy, macro-F1, per-class drop, calibration, safety-net behaviour
make fewshot    # accuracy vs k = 5, 10, 20 GB photos per class (pool and test split by plant + leaf id)
make report     # README / MODEL_CARD numbers refresh from results/
make package    # new zip; the Field Intelligence page picks up results/shift/field_gap.json automatically
```
