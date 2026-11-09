"""ONNX parity: the exported model and the app's NumPy preprocessing match PyTorch/torchvision."""

from __future__ import annotations

import json

import numpy as np
import pytest
import torch
from PIL import Image

from app.services.diseases import slug as backend_slug
from app.services.preprocess import preprocess as app_preprocess
from cropdoc import paths
from cropdoc.data.classes import CLASS_IDS, slug
from cropdoc.data.transforms import eval_transform
from cropdoc.models.camnet import CamNet
from cropdoc.models.small_cnn import SmallCNNFeatures
from cropdoc.quick import export_onnx


@pytest.mark.parametrize("size", [(256, 256), (640, 480), (300, 900), (231, 224)])
def test_app_preprocessing_matches_torchvision(size):
    rng = np.random.default_rng(sum(size))
    image = Image.fromarray(rng.integers(0, 255, size=(size[1], size[0], 3), dtype=np.uint8))
    expected = eval_transform()(image).numpy()[None]
    actual, crop = app_preprocess(image)
    assert actual.shape == expected.shape == (1, 3, 224, 224)
    assert np.abs(actual - expected).max() < 1e-5
    assert crop.size == (224, 224)


def test_onnx_export_matches_pytorch(tmp_path):
    import onnxruntime as ort

    torch.manual_seed(0)
    model = CamNet(SmallCNNFeatures(widths=(8, 8, 16, 16)), 16, num_classes=5).eval()
    path = export_onnx(model, tmp_path / "tiny.onnx")
    x = torch.randn(3, 3, 224, 224)
    with torch.inference_mode():
        t_logits, t_cams = model.forward_with_cams(x)
    session = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
    o_logits, o_cams = session.run(["logits", "cams"], {"image": x.numpy()})
    assert np.abs(t_logits.numpy() - o_logits).max() < 1e-4
    assert np.abs(t_cams.numpy() - o_cams).max() < 1e-4
    assert o_cams.shape == (3, 5, 7, 7)


def test_slug_is_identical_in_ml_and_backend():
    assert all(slug(c) == backend_slug(c) for c in CLASS_IDS)
    assert len({slug(c) for c in CLASS_IDS}) == len(CLASS_IDS)


@pytest.mark.model
@pytest.mark.skipif(not (paths.MODELS_ACTIVE / "model.onnx").exists(), reason="no trained model installed")
def test_active_model_package_is_complete():
    import onnxruntime as ort

    session = ort.InferenceSession(
        str(paths.MODELS_ACTIVE / "model.onnx"), providers=["CPUExecutionProvider"]
    )
    logits, cams = session.run(["logits", "cams"], {"image": np.zeros((2, 3, 224, 224), np.float32)})
    classes = json.loads((paths.MODELS_ACTIVE / "classes.json").read_text())["classes"]
    assert logits.shape == (2, len(classes)) and cams.shape[:2] == (2, len(classes))
    card = json.loads((paths.MODELS_ACTIVE / "model_card.json").read_text())
    assert 0.0 < card["metrics"]["test_accuracy"] <= 1.0 and card["metrics"]["source"].startswith("results/")
    calibration = json.loads((paths.MODELS_ACTIVE / "calibration.json").read_text())
    assert calibration["temperature"] > 0
