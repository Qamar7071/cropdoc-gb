"""Background uniformity and background-only probes (``make background``).

If a classifier that sees ONLY the background (never the leaf) beats chance by a wide margin, the
background carries label information: a shortcut a model can exploit in the lab that disappears in
real fields. Probes (logistic regression on colour statistics, group-aware split, sampled photos):
  * border-only: an 8-pixel frame around the photo,
  * background-only: every pixel outside the leaf mask (from the segmented twin).
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd
from PIL import Image
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score
from sklearn.preprocessing import StandardScaler

from cropdoc import paths
from cropdoc.data.manifest import absolute
from cropdoc.research.common import load_split, log
from cropdoc.research.masks import leaf_mask
from cropdoc.utils import write_json

BORDER = 8
PER_CLASS = {"train": 400, "test": 150}


def colour_stats(pixels: np.ndarray) -> np.ndarray:
    """HSV histograms (16 bins per channel) + RGB mean/std of a set of pixels (N×3 uint8)."""
    if len(pixels) == 0:
        return np.zeros(16 * 3 + 6, dtype=np.float32)
    hsv = np.asarray(Image.fromarray(pixels.reshape(1, -1, 3)).convert("HSV")).reshape(-1, 3)
    hist = np.concatenate(
        [np.histogram(hsv[:, c], bins=16, range=(0, 255), density=True)[0] for c in range(3)]
    )
    return np.concatenate([hist, pixels.mean(0) / 255, pixels.std(0) / 255]).astype(np.float32)


def photo_features(row: tuple[str, str]) -> tuple[np.ndarray, np.ndarray, float, float]:
    path, seg_path = row
    with Image.open(absolute(path)) as image:
        rgb = np.asarray(image.convert("RGB"))
    frame = np.ones(rgb.shape[:2], dtype=bool)
    frame[BORDER:-BORDER, BORDER:-BORDER] = False
    border_pixels = rgb[frame]
    mask = leaf_mask(seg_path, size=(rgb.shape[1], rgb.shape[0]))
    background_pixels = rgb[~mask]
    return (
        colour_stats(border_pixels),
        colour_stats(background_pixels),
        float(border_pixels.std(0).mean() / 255),
        float((~mask).mean()),
    )


def probe(x_tr, y_tr, x_te, y_te) -> dict:
    scaler = StandardScaler().fit(x_tr)
    model = LogisticRegression(max_iter=3000).fit(scaler.transform(x_tr), y_tr)
    preds = model.predict(scaler.transform(x_te))
    return {
        "accuracy": float(accuracy_score(y_te, preds)),
        "macro_f1": float(f1_score(y_te, preds, average="macro")),
    }


def main() -> int:
    frame = load_split("group_aware")
    manifest = pd.read_csv(paths.CACHE / "manifest.csv", keep_default_na=False)[["path", "seg_path"]]
    frame = frame.merge(manifest, on="path")
    frame = frame[frame.seg_path != ""]
    parts = []
    for split, per_class in PER_CLASS.items():
        subset = frame[frame.split == split]
        parts.append(
            pd.concat([g.sample(min(per_class, len(g)), random_state=0) for _, g in subset.groupby("label")])
        )
    sample = pd.concat(parts).reset_index(drop=True)
    log.info("background probes on %d photos", len(sample))
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(photo_features, zip(sample.path, sample.seg_path, strict=True), chunksize=64))
    border = np.stack([r[0] for r in results])
    background = np.stack([r[1] for r in results])
    border_std = np.array([r[2] for r in results])
    background_area = np.array([r[3] for r in results])

    tr, te = sample.split.to_numpy() == "train", sample.split.to_numpy() == "test"
    y = sample.label.to_numpy()
    counts = np.bincount(y[te], minlength=38)
    per_class_border = (
        sample.assign(border_std=border_std).groupby("class_id").border_std.mean().sort_values()
    )
    write_json(
        paths.RESULTS / "background" / "background_summary.json",
        {
            "n_photos": int(len(sample)),
            "sampling": f"up to {PER_CLASS['train']} train / {PER_CLASS['test']} test photos per class (group-aware split)",
            "border_pixel_std_mean": float(border_std.mean()),
            "background_area_fraction_mean": float(background_area.mean()),
            "most_uniform_backgrounds": per_class_border.head(5).round(4).to_dict(),
            "least_uniform_backgrounds": per_class_border.tail(5).round(4).to_dict(),
            "border_only_probe": probe(border[tr], y[tr], border[te], y[te]),
            "background_only_probe": probe(background[tr], y[tr], background[te], y[te]),
            "chance_accuracy": 1 / 38,
            "majority_class_accuracy": float(counts.max() / counts.sum()),
            "note": "Probes never see leaf pixels. Accuracy far above chance means the background predicts the class.",
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
