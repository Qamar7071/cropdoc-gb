# Data

Nothing in this folder is committed to git except this README and `field_test/README.md`.

## 1. Automatic download (no API keys needed)
```bash
python scripts/download_data.py --plantdoc    # or: make data
```
This uses git sparse checkout to fetch only what we need:

| Dataset | Source | What we fetch | License |
|---|---|---|---|
| PlantVillage | https://github.com/spMohanty/PlantVillage-Dataset | `raw/color` (54,305 photos, 38 classes), `raw/segmented` (background-removed twins → leaf masks), `leaf-map.json` (photo → physical leaf) | CC BY-SA 3.0 |
| PlantDoc | https://github.com/pratikkayal/PlantDoc-Dataset | `train/`, `test/` (real-world web photos, 28 classes) | CC BY 4.0 |

The exact commit of each download is recorded in `data/raw/SOURCES.json`.

Resulting layout:
```
data/raw/PlantVillage-Dataset/raw/color/<class>/<file>.JPG
data/raw/PlantVillage-Dataset/raw/segmented/<class>/<file>_final_masked.jpg
data/raw/PlantVillage-Dataset/leaf-map.json
data/raw/PlantDoc-Dataset/{train,test}/<class>/<file>
```

## 2. Manual fallback (if git is blocked on your network)
1. Open https://github.com/spMohanty/PlantVillage-Dataset, click **Code → Download ZIP**
   (large: it contains colour, grayscale and segmented copies), unzip, and move the folder so the
   layout above holds (rename it `PlantVillage-Dataset`).
2. Alternative: Kaggle dataset "PlantVillage Dataset" (needs a free Kaggle account and an API key in
   `~/.kaggle/kaggle.json`): `kaggle datasets download -d abdallahalidev/plantvillage-dataset`, then
   place `color/` and `segmented/` under `data/raw/PlantVillage-Dataset/raw/`. The Kaggle copy has no
   `leaf-map.json`; download that single file from the GitHub repo.
3. PlantDoc: **Code → Download ZIP** on https://github.com/pratikkayal/PlantDoc-Dataset, unzip to
   `data/raw/PlantDoc-Dataset`.

## 3. Your Gilgit-Baltistan field photos
Put them in `data/field_test/<class_id>/` (class ids are the PlantVillage folder names, e.g.
`Potato___Late_blight`). Read `docs/field_collection_guide.md` first: how many photos, angles,
lighting, backgrounds, file naming, and how to keep photos of the same leaf together.

## 4. Created at runtime
- `data/app/` — the app's SQLite database (saved scans). Delete it to reset your history.
- `data/inbox/` — photos contributed through the app (unverified labels).
