"""Calibrate the app's photo-quality check on validation photos (``make quality``).

Rule (fixed in advance, validation photos only): each check may flag at most 1% of the domain-balanced
validation set (lab val sample + field val, equal weight):
  * too dark   : brightness below the 1st percentile
  * too bright : brightness above the 99th percentile
  * blurry     : sharpness below the 1st percentile
Then the detection power is REPORTED on synthetically degraded copies of the same photos (darkened,
washed out, defocused) and the false-alarm rate on lab and field test photos.
Writes results/quality/quality_summary.json and models/active/quality.json (read by the web app).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from PIL import Image, ImageEnhance, ImageFilter

from cropdoc import paths
from cropdoc.data.datasets import load_rgb
from cropdoc.data.manifest import absolute
from cropdoc.quality import measure
from cropdoc.quick import balanced_subset, load_split
from cropdoc.utils import get_logger, write_json

log = get_logger("quality")
FIELD_SPLIT = paths.SPLITS / "plantdoc_group_aware.csv.gz"


def degrade(image: Image.Image, kind: str) -> Image.Image:
    if kind == "dark":
        return ImageEnhance.Brightness(image).enhance(0.15)
    if kind == "bright":
        return Image.blend(image, Image.new("RGB", image.size, (255, 255, 255)), 0.8)
    if kind == "blur":  # defocus: blur radius ~1.5% of the long side
        return image.filter(ImageFilter.GaussianBlur(radius=max(2.0, 0.015 * max(image.size))))
    return image


def metrics(frame: pd.DataFrame, kind: str = "none") -> pd.DataFrame:
    rows = [measure(degrade(load_rgb(absolute(p)), kind)) for p in frame.path]
    return pd.DataFrame(rows)


def flagged(m: pd.DataFrame, t: dict) -> dict:
    dark = m.brightness < t["min_brightness"]
    bright = m.brightness > t["max_brightness"]
    blurry = m.sharpness < t["min_sharpness"]
    return {
        "n": int(len(m)),
        "too_dark": float(dark.mean()),
        "too_bright": float(bright.mean()),
        "blurry": float(blurry.mean()),
        "any": float((dark | bright | blurry).mean()),
    }


def main() -> int:
    lab = load_split("group_aware")
    field = pd.read_csv(FIELD_SPLIT)
    lab_val = balanced_subset(lab[lab.split == "val"], 40, seed=0)
    field_val = field[field.split == "val"]
    lab_test = balanced_subset(lab[lab.split == "test"], 20, seed=0)
    field_test = field[field.split == "test"]
    log.info("measuring %d lab val + %d field val photos", len(lab_val), len(field_val))
    m_lab, m_field = metrics(lab_val), metrics(field_val)
    repeat = max(1, round(len(m_lab) / len(m_field)))
    balanced = pd.concat([m_lab, *([m_field] * repeat)], ignore_index=True)
    thresholds = {
        "min_brightness": float(np.percentile(balanced.brightness, 1)),
        "max_brightness": float(np.percentile(balanced.brightness, 99)),
        "min_sharpness": float(np.percentile(balanced.sharpness, 1)),
    }
    log.info("thresholds %s", thresholds)
    report = {
        "rule": "each check flags at most 1% of the domain-balanced validation photos (lab val sample + field val)",
        "thresholds": thresholds,
        "validation": {"lab": flagged(m_lab, thresholds), "field": flagged(m_field, thresholds)},
        "false_alarms_on_test_photos": {
            "lab": flagged(metrics(lab_test), thresholds),
            "field": flagged(metrics(field_test), thresholds),
        },
        "detection_on_degraded_validation_photos": {},
        "note": "Field photos are PlantDoc web photos, not Gilgit-Baltistan photos. Degraded copies are synthetic.",
    }
    both = pd.concat([lab_val, field_val], ignore_index=True)
    for kind in ("dark", "bright", "blur"):
        report["detection_on_degraded_validation_photos"][kind] = flagged(metrics(both, kind), thresholds)
    write_json(paths.RESULTS / "quality" / "quality_summary.json", report)
    write_json(
        paths.MODELS_ACTIVE / "quality.json",
        {
            "thresholds": thresholds,
            "source": "Validation photos only (results/quality/quality_summary.json): each check flags at most 1% of "
            "domain-balanced validation photos. Detection on synthetic dark/bright/blurred copies is reported there.",
        },
    )
    log.info("detection on degraded photos: %s", report["detection_on_degraded_validation_photos"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
