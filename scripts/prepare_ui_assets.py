"""Copy real PlantVillage photos into the frontend (Quick Examples + Disease Library pictures).

* Quick Examples: one photo per example class, drawn at random (fixed seed) from the TEST split,
  without looking at the model's prediction (no cherry-picking).
* Library: three photos per class from the TRAIN split, for the library carousel and the
  "compare with a reference photo" view in History.
Photos are re-encoded (no metadata). License: PlantVillage, CC BY-SA 3.0 (attribution written).
"""

from __future__ import annotations

import gzip
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml" / "src"))

import pandas as pd  # noqa: E402
from PIL import Image  # noqa: E402

from cropdoc import paths  # noqa: E402
from cropdoc.data.classes import CLASS_IDS, class_info, slug  # noqa: E402
from cropdoc.data.manifest import absolute  # noqa: E402

PUBLIC = ROOT / "frontend" / "public"
EXAMPLES = [
    ("early-blight", "Potato___Early_blight", "examples.earlyBlight"),
    ("yellow-leaf-curl", "Tomato___Tomato_Yellow_Leaf_Curl_Virus", "examples.yellowLeafCurl"),
    ("powdery-mildew", "Squash___Powdery_mildew", "examples.powderyMildew"),
    ("healthy-leaf", "Tomato___healthy", "examples.healthyLeaf"),
]
ATTRIBUTION = (
    "Leaf photos: PlantVillage dataset (D. P. Hughes, M. Salathé; https://github.com/spMohanty/PlantVillage-Dataset), "
    "licensed CC BY-SA 3.0. Re-encoded without metadata; unchanged otherwise."
)


def save_clean(source: Path, target: Path, max_side: int = 512) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as image:
        rgb = image.convert("RGB")
        rgb.thumbnail((max_side, max_side))
        rgb.save(target, format="JPEG", quality=90, optimize=True)


def main() -> int:
    with gzip.open(paths.SPLITS / "group_aware.csv.gz", "rb") as fh:
        frame = pd.read_csv(io.BytesIO(fh.read()))

    examples = []
    for key, class_id, label_key in EXAMPLES:
        row = frame[(frame.class_id == class_id) & (frame.split == "test")].sample(1, random_state=7).iloc[0]
        save_clean(absolute(row.path), PUBLIC / "examples" / f"{key}.jpg")
        examples.append(
            {
                "id": key,
                "file": f"/examples/{key}.jpg",
                "class_id": class_id,
                "label_key": label_key,
                "split": "test",
                "source": row.path,
            }
        )
    (PUBLIC / "examples" / "examples.json").write_text(
        json.dumps({"attribution": ATTRIBUTION, "examples": examples}, indent=2)
    )

    index = {}
    for class_id in CLASS_IDS:
        rows = frame[(frame.class_id == class_id) & (frame.split == "train")].sample(3, random_state=11)
        folder = PUBLIC / "library" / slug(class_id)
        urls = []
        for n, row in enumerate(rows.itertuples(), start=1):
            save_clean(absolute(row.path), folder / f"{n}.jpg", max_side=384)
            urls.append(f"/library/{slug(class_id)}/{n}.jpg")
        index[class_id] = {"crop": class_info(class_id).crop, "images": urls}
    (PUBLIC / "library" / "index.json").write_text(
        json.dumps({"attribution": ATTRIBUTION, "classes": index}, indent=2)
    )
    (PUBLIC / "library" / "ATTRIBUTION.txt").write_text(ATTRIBUTION + "\n")
    print(f"wrote {len(examples)} examples and {3 * len(index)} library photos to {PUBLIC}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
