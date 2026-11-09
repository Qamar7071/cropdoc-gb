"""Can the model tell when it should not answer? (``make ood``)

Scores (higher = "this looks unfamiliar"): 1 − max-softmax probability (MSP) and the energy score.
  * near-OOD, unseen diseases: a linear head on frozen features trained WITHOUT 4 diseases (chosen
    in advance, one per crop); those diseases' test photos are the unfamiliar set;
  * far-OOD, non-leaf photos: the deployed model on everyday-object photos (ImageNet sample, plant and
    fungus classes removed), including what the app's real thresholds do with them;
  * shift: real-world leaf photos (PlantDoc) vs lab test photos, which explains why the app often says
    "unsupported" in the field.
AUROC: 0.5 = no better than a coin, 1.0 = perfect separation.
"""

from __future__ import annotations

import numpy as np
import torch

from cropdoc import paths
from cropdoc.data.classes import CLASS_IDS
from cropdoc.embeddings import compute_embeddings
from cropdoc.quick import train_linear_probe
from cropdoc.research.common import energy, imagenet_ood_frame, load_split, log, plantdoc_frame, softmax
from cropdoc.research.shift_eval import cached_logits, safety_net
from cropdoc.stats import auroc, fpr_at_tpr
from cropdoc.utils import read_json, write_json

HOLDOUT = [
    "Tomato___Target_Spot",
    "Apple___Cedar_apple_rust",
    "Grape___Esca_(Black_Measles)",
    "Corn_(maize)___Common_rust_",
]
ARCH = "mobilenetv3_large_100"


def scores(logits: np.ndarray, temperature: float = 1.0) -> dict[str, np.ndarray]:
    return {"msp": 1 - softmax(logits, temperature).max(1), "energy": energy(logits)}


def compare(name: str, kind: str, model: str, id_logits, ood_logits, temperature: float = 1.0) -> dict:
    s_in, s_out = scores(id_logits, temperature), scores(ood_logits, temperature)
    return {
        "name": name,
        "kind": kind,
        "model": model,
        "n_id": int(len(id_logits)),
        "n_ood": int(len(ood_logits)),
        "auroc_msp": auroc(s_in["msp"], s_out["msp"]),
        "auroc_energy": auroc(s_in["energy"], s_out["energy"]),
        "fpr95_msp": fpr_at_tpr(s_in["msp"], s_out["msp"]),
        "fpr95_energy": fpr_at_tpr(s_in["energy"], s_out["energy"]),
    }


def near_ood() -> dict:
    split = load_split("group_aware")
    x = compute_embeddings(split[["path"]], ARCH)
    held = split.class_id.isin(HOLDOUT).to_numpy()
    known = [c for c in CLASS_IDS if c not in HOLDOUT]
    remap = {CLASS_IDS.index(c): i for i, c in enumerate(known)}
    y = np.array([remap.get(v, -1) for v in split.label])
    s = split.split.to_numpy()
    tr, va = (s == "train") & ~held, (s == "val") & ~held
    result = train_linear_probe(x[tr], y[tr], x[va], y[va], num_classes=len(known), seed=0)
    layer = torch.nn.Linear(x.shape[1], len(known))
    with torch.no_grad():
        layer.weight.copy_(torch.from_numpy(result.weight))
        layer.bias.copy_(torch.from_numpy(result.bias))
        logits = layer(torch.from_numpy(x)).numpy()
    test = s == "test"
    entry = compare(
        "Unseen diseases (4 held out)",
        "near",
        "frozen features + linear head (34 classes)",
        logits[test & ~held],
        logits[test & held],
    )
    entry["held_out_classes"] = HOLDOUT
    entry["id_accuracy"] = float((logits[test & ~held].argmax(1) == y[test & ~held]).mean())
    return entry


def main() -> int:
    calibration = read_json(paths.MODELS_ACTIVE / "calibration.json")
    temperature = calibration["temperature"]
    lab = np.load(paths.CACHE / "quick_logits.npz")
    lab_logits = lab["test"]
    sets = [near_ood()]
    log.info("near-OOD: %s", sets[-1])

    imagenet = imagenet_ood_frame()
    if len(imagenet):
        im_logits = cached_logits("imagenet_ood", imagenet)
        entry = compare(
            "Non-leaf photos (everyday objects)",
            "far",
            "deployed quick model",
            lab_logits,
            im_logits,
            temperature,
        )
        app = safety_net(im_logits, np.full(len(im_logits), -1), temperature, calibration["thresholds"])
        entry["deployed_thresholds"] = {k: v["share"] for k, v in app.items()}
        sets.append(entry)
        log.info("far-OOD: %s", entry)

    plantdoc = plantdoc_frame()
    pd_logits = cached_logits("plantdoc", plantdoc)
    sets.append(
        compare(
            "Real-world leaf photos (PlantDoc) vs lab photos",
            "shift",
            "deployed quick model",
            lab_logits,
            pd_logits,
            temperature,
        )
    )
    write_json(
        paths.RESULTS / "ood" / "ood_summary.json",
        {
            "id_set": "PlantVillage group-aware test split",
            "score_direction": "higher = more unfamiliar",
            "sets": sets,
            "thresholds_in_app": calibration["thresholds"],
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
