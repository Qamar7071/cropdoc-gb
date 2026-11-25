"""Load the exported model (ONNX) and turn one photo into a prediction.

Model package (``models/active/``):
* ``model.onnx``       input ``image`` [N,3,224,224]; outputs ``logits`` [N,C] and ``cams`` [N,C,h,w]
* ``classes.json``     class ids in output order, with crop and disease names
* ``calibration.json`` temperature (confidence calibration) and decision thresholds
* ``model_card.json``  real measured metrics, shown by /api/health and the About page

If the package is missing the service reports ``loaded = False`` and the API refuses to predict
(it never invents a result).
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from app.services import gradcam
from app.services.ood import Thresholds, decide_status, energy_score, softmax
from app.services.preprocess import CROP, RESIZE, preprocess

NOT_LOADED_HELP = (
    "Model not loaded. Train the quick model with `python scripts/train_quick.py` "
    "(or run ml/notebooks/colab_run.ipynb) so that models/active/model.onnx exists, then restart."
)
VC_REDIST_URL = "https://aka.ms/vs/17/release/vc_redist.x64.exe"


def runtime_help(exc: BaseException, platform: str | None = None) -> str:
    """Actionable message when ONNX Runtime itself cannot start (the model files are fine)."""
    platform = platform or sys.platform
    detail = str(exc).strip()
    if platform.startswith("win") and "DLL load failed" in detail:
        return (
            "The AI engine (ONNX Runtime) could not start on this Windows computer: a Microsoft system "
            "library it needs is missing or outdated. Fix: install the latest Microsoft Visual C++ "
            f"Redistributable (x64) from {VC_REDIST_URL}, restart the computer if the installer asks, "
            "then run start.bat again. If it still fails, see 'Troubleshooting' in README.md. "
            f"(Technical detail: {detail})"
        )
    return (
        "The AI engine (ONNX Runtime) could not be imported. Re-run the start script so it can reinstall "
        f"the dependencies; see 'Troubleshooting' in README.md. (Technical detail: {detail})"
    )


@dataclass
class ClassInfo:
    """One output class of the model."""

    id: str
    crop: str
    disease: str
    healthy: bool


@dataclass
class InferenceService:
    """Wraps an ONNX Runtime session plus class names, calibration and the model card."""

    loaded: bool = False
    reason: str = NOT_LOADED_HELP
    classes: list[ClassInfo] = field(default_factory=list)
    model_card: dict[str, Any] = field(default_factory=dict)
    calibration: dict[str, Any] = field(default_factory=dict)
    session: Any = None
    temperature: float = 1.0
    thresholds: Thresholds = field(default_factory=Thresholds)
    resize: int = RESIZE
    crop_size: int = CROP

    @classmethod
    def load(cls, model_dir: Path) -> InferenceService:
        """Load the model package; return a not-loaded service (with the reason) on any problem."""
        model_path = model_dir / "model.onnx"
        classes_path = model_dir / "classes.json"
        if not model_path.exists() or not classes_path.exists():
            return cls(loaded=False, reason=NOT_LOADED_HELP)
        try:
            import onnxruntime as ort
        except ImportError as exc:  # engine problem (e.g. missing Windows runtime), not a model problem
            return cls(loaded=False, reason=runtime_help(exc))
        try:
            options = ort.SessionOptions()
            options.log_severity_level = 3
            session = ort.InferenceSession(str(model_path), options, providers=["CPUExecutionProvider"])
            classes = [
                ClassInfo(**c) for c in json.loads(classes_path.read_text(encoding="utf-8"))["classes"]
            ]
            card = _read_json(model_dir / "model_card.json")
            calibration = _read_json(model_dir / "calibration.json")
        except Exception as exc:  # corrupted package → clear message instead of a crash
            return cls(loaded=False, reason=f"Model files could not be loaded ({exc}). {NOT_LOADED_HELP}")
        prep = card.get("preprocessing", {})
        return cls(
            loaded=True,
            reason="",
            classes=classes,
            model_card=card,
            calibration=calibration,
            session=session,
            temperature=float(calibration.get("temperature", 1.0)),
            thresholds=Thresholds.from_dict(calibration.get("thresholds")),
            resize=int(prep.get("resize", RESIZE)),
            crop_size=int(prep.get("crop", CROP)),
        )

    @property
    def version(self) -> str:
        """Model version string from the model card."""
        return str(self.model_card.get("model_version", "unknown"))

    @property
    def crops(self) -> list[str]:
        """Supported crops (for the crop-hint selector)."""
        return sorted({c.crop for c in self.classes})

    def class_index(self, class_id: str) -> int | None:
        """Output index of a class id, or None."""
        for index, info in enumerate(self.classes):
            if info.id == class_id:
                return index
        return None

    def predict(self, image: Image.Image, crop_hint: str | None = None) -> dict[str, Any]:
        """Run the model on one PIL image and build the full result (without saving anything)."""
        if not self.loaded:
            raise RuntimeError(self.reason)
        array, model_view = preprocess(image, self.resize, self.crop_size)
        logits, cams = self.session.run(["logits", "cams"], {"image": array})
        logits = logits[0].astype(np.float64)
        scaled = logits / self.temperature

        allowed = np.ones(len(self.classes), dtype=bool)
        if crop_hint:
            allowed = np.array([c.crop.lower() == crop_hint.lower() for c in self.classes])
        masked = np.where(allowed, scaled, -np.inf)
        probs = softmax(masked)
        order = [int(i) for i in np.argsort(-probs)[:3] if allowed[i]]
        top = order[0]

        confidence = float(probs[top])
        energy = float(energy_score(logits[None], 1.0)[0])
        status = decide_status(confidence, energy, self.thresholds)

        heat = gradcam.heatmap_image(cams[0, top], model_view.size)
        return {
            "status": status,
            "class_id": self.classes[top].id,
            "crop": self.classes[top].crop,
            "disease": self.classes[top].disease,
            "healthy": self.classes[top].healthy,
            "confidence": confidence,
            "top3": [
                {
                    "class_id": self.classes[i].id,
                    "crop": self.classes[i].crop,
                    "disease": self.classes[i].disease,
                    "probability": float(probs[i]),
                }
                for i in order
            ],
            "scores": {"max_softmax": confidence, "energy": energy},
            "thresholds": {
                "min_confidence": self.thresholds.min_confidence,
                "max_energy": self.thresholds.max_energy,
                "provisional": self.thresholds.provisional,
                "source": self.thresholds.source,
            },
            "crop_hint": crop_hint,
            "model_version": self.version,
            "images": {
                "model_view": model_view,
                "heatmap": heat,
                "overlay": gradcam.overlay(model_view, heat),
            },
        }


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
