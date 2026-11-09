"""Does the model look at the leaf? Grad-CAM focus + interventions (``make explain``).

* CAM mass outside the leaf: share of the (ReLU) Grad-CAM heat on background pixels, compared with
  the background's share of the image (what a uniform heatmap would give). Ratio < 1 means the
  model concentrates on the leaf more than chance.
* Interventions that need no heatmap at all:
  - leaf removed (leaf pixels painted grey): any accuracy above chance comes from the background;
  - background removed (leaf on black): accuracy without background cues.
* Confusion matrix, top confusions and a gallery of correct and wrong predictions with heatmaps.
"""

from __future__ import annotations

import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import torch  # noqa: E402
from PIL import Image  # noqa: E402
from sklearn.metrics import confusion_matrix  # noqa: E402

from cropdoc import paths  # noqa: E402
from cropdoc.data.classes import CLASS_IDS, class_info  # noqa: E402
from cropdoc.data.manifest import absolute  # noqa: E402
from cropdoc.data.transforms import eval_transform  # noqa: E402
from cropdoc.research.common import load_split, log  # noqa: E402
from cropdoc.research.masks import leaf_mask, model_view_mask  # noqa: E402
from cropdoc.utils import write_json  # noqa: E402

MODEL = paths.MODELS_ACTIVE / "model.onnx"
OUT = paths.RESULTS / "explain"
PER_CLASS = 40
BORDER = 16


def session():
    import onnxruntime as ort

    options = ort.SessionOptions()
    options.intra_op_num_threads = os.cpu_count() or 4
    return ort.InferenceSession(str(MODEL), options, providers=["CPUExecutionProvider"])


def run(sess, images: list[Image.Image]) -> tuple[np.ndarray, np.ndarray]:
    transform = eval_transform()
    batch = torch.stack([transform(im) for im in images]).numpy()
    logits, cams = sess.run(["logits", "cams"], {"image": batch})
    return logits, cams


def upsample(cam: np.ndarray) -> np.ndarray:
    tensor = torch.from_numpy(np.maximum(cam, 0).astype(np.float32))[None, None]
    return torch.nn.functional.interpolate(tensor, size=(224, 224), mode="bilinear", align_corners=False)[
        0, 0
    ].numpy()


def main() -> int:
    split = load_split("group_aware")
    manifest = pd.read_csv(paths.CACHE / "manifest.csv", keep_default_na=False)[["path", "seg_path"]]
    test = split[split.split == "test"].merge(manifest, on="path")
    test = test[test.seg_path != ""]
    sample = pd.concat(
        [g.sample(min(PER_CLASS, len(g)), random_state=0) for _, g in test.groupby("label")]
    ).reset_index(drop=True)
    log.info("explainability on %d test photos", len(sample))
    sess = session()
    frame_mask = np.ones((224, 224), dtype=bool)
    frame_mask[BORDER:-BORDER, BORDER:-BORDER] = False

    records, gallery = [], []
    for start in range(0, len(sample), 32):
        rows = sample.iloc[start : start + 32]
        originals, no_leaf, no_background, masks = [], [], [], []
        for row in rows.itertuples():
            with Image.open(absolute(row.path)) as image:
                rgb = image.convert("RGB")
            mask = leaf_mask(row.seg_path, size=rgb.size)
            array = np.asarray(rgb).copy()
            painted = array.copy()
            painted[mask] = 128  # leaf removed → grey
            black = array.copy()
            black[~mask] = 0  # background removed → black
            originals.append(rgb)
            no_leaf.append(Image.fromarray(painted))
            no_background.append(Image.fromarray(black))
            masks.append(model_view_mask(mask))
        logits, cams = run(sess, originals)
        logits_no_leaf, _ = run(sess, no_leaf)
        logits_no_bg, _ = run(sess, no_background)
        preds = logits.argmax(1)
        for i, row in enumerate(rows.itertuples()):
            heat = upsample(cams[i, preds[i]])
            total = heat.sum() + 1e-12
            leaf = masks[i]
            outside = float(heat[~leaf].sum() / total)
            area = float((~leaf).mean())
            records.append(
                {
                    "class_id": row.class_id,
                    "label": row.label,
                    "pred": int(preds[i]),
                    "correct": bool(preds[i] == row.label),
                    "cam_outside_leaf": outside,
                    "background_area": area,
                    "cam_in_border": float(heat[frame_mask].sum() / total),
                    "border_area": float(frame_mask.mean()),
                    "pred_leaf_removed": int(logits_no_leaf[i].argmax()),
                    "pred_background_removed": int(logits_no_bg[i].argmax()),
                }
            )
            if len(gallery) < 400:
                gallery.append((originals[i], heat, row.class_id, CLASS_IDS[preds[i]], preds[i] == row.label))

    df = pd.DataFrame(records)
    df["ratio"] = df.cam_outside_leaf / df.background_area.clip(lower=1e-3)
    OUT.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT / "cam_per_photo.csv", index=False)

    # confusion matrix on the full test split (cached logits from training)
    lab = np.load(paths.CACHE / "quick_logits.npz")
    cm = confusion_matrix(lab["y_test"], lab["test"].argmax(1), labels=range(len(CLASS_IDS)))
    off = cm.copy()
    np.fill_diagonal(off, 0)
    top = np.dstack(np.unravel_index(np.argsort(-off.ravel())[:10], off.shape))[0]
    fig, ax = plt.subplots(figsize=(11, 10))
    ax.imshow(cm / cm.sum(1, keepdims=True), cmap="Greens")
    names = [f"{class_info(c).crop}: {class_info(c).disease}" for c in CLASS_IDS]
    ax.set_xticks(range(len(names)), names, rotation=90, fontsize=6)
    ax.set_yticks(range(len(names)), names, fontsize=6)
    ax.set(
        xlabel="predicted", ylabel="true", title="Confusion matrix (group-aware test split, row-normalized)"
    )
    fig.tight_layout()
    fig.savefig(OUT / "confusion_matrix.png", dpi=150)
    plt.close(fig)

    # gallery: 8 correct + up to 8 wrong
    picks = [g for g in gallery if g[4]][:8] + [g for g in gallery if not g[4]][:8]
    fig, axes = plt.subplots(2, 8, figsize=(16, 4.8))
    for ax, (image, heat, true_id, pred_id, ok) in zip(axes.ravel(), picks, strict=False):
        view = np.asarray(eval_transform().transforms[1](eval_transform().transforms[0](image)))
        ax.imshow(view)
        ax.imshow(heat, cmap="jet", alpha=0.45)
        ax.set_title(
            f"{'✓' if ok else '✗'} {class_info(pred_id).disease}\ntrue: {class_info(true_id).disease}",
            fontsize=7,
        )
        ax.axis("off")
    for ax in axes.ravel()[len(picks) :]:
        ax.axis("off")
    fig.suptitle("Grad-CAM on lab test photos: top row correct, bottom row wrong (red = most influential)")
    fig.tight_layout()
    fig.savefig(OUT / "gallery.png", dpi=130)
    plt.close(fig)

    labels = df.label.to_numpy()
    write_json(
        OUT / "cam_outside_leaf.json",
        {
            "model_version": "deployed quick model",
            "n_images": int(len(df)),
            "sampling": f"up to {PER_CLASS} group-aware test photos per class with a leaf mask",
            "cam_mass_outside_leaf_mean": float(df.cam_outside_leaf.mean()),
            "background_area_fraction_mean": float(df.background_area.mean()),
            "outside_to_area_ratio_median": float(df.ratio.median()),
            "cam_mass_in_border_mean": float(df.cam_in_border.mean()),
            "border_area_fraction": float(df.border_area.iloc[0]),
            "correct_vs_wrong_cam_outside": {
                "correct": float(df[df.correct].cam_outside_leaf.mean()),
                "wrong": float(df[~df.correct].cam_outside_leaf.mean()) if (~df.correct).any() else None,
            },
            "accuracy_original": float((df.pred == labels).mean()),
            "accuracy_leaf_removed": float((df.pred_leaf_removed == labels).mean()),
            "accuracy_background_removed": float((df.pred_background_removed == labels).mean()),
            "chance_accuracy": 1 / 38,
            "top_confusions": [
                {"true": CLASS_IDS[i], "predicted": CLASS_IDS[j], "count": int(off[i, j])}
                for i, j in top
                if off[i, j] > 0
            ],
            "figures": ["results/explain/gallery.png", "results/explain/confusion_matrix.png"],
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
