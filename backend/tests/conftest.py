"""Test fixtures: a tiny generated ONNX model (no PyTorch needed) and an app factory.

The tiny model has the same interface as the real one (inputs ``image``; outputs ``logits`` and
``cams``) so every API path can be tested without downloading data or training anything.
Its metrics block is clearly marked as a test fixture, not a real result.
"""

from __future__ import annotations

import io
import json
from collections.abc import Callable, Iterator
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.config import Settings
from app.main import create_app

FIXTURE_CLASSES = [
    {"id": "Potato___Early_blight", "crop": "Potato", "disease": "Early blight", "healthy": False},
    {"id": "Potato___healthy", "crop": "Potato", "disease": "Healthy", "healthy": True},
    {"id": "Tomato___Late_blight", "crop": "Tomato", "disease": "Late blight", "healthy": False},
]


def build_tiny_onnx(path: Path, num_classes: int = 3, seed: int = 0) -> None:
    """Conv(stride 32) → ReLU → GAP → Linear, plus CAM = einsum(W, features)."""
    import onnx
    from onnx import TensorProto, helper, numpy_helper

    rng = np.random.default_rng(seed)
    conv_w = rng.normal(0, 0.05, size=(4, 3, 32, 32)).astype(np.float32)
    fc_w = rng.normal(0, 1.0, size=(num_classes, 4)).astype(np.float32)
    fc_b = np.zeros(num_classes, dtype=np.float32)
    nodes = [
        helper.make_node("Conv", ["image", "conv_w"], ["conv"], strides=[32, 32]),
        helper.make_node("Relu", ["conv"], ["features"]),
        helper.make_node("GlobalAveragePool", ["features"], ["pooled"]),
        helper.make_node("Flatten", ["pooled"], ["flat"], axis=1),
        helper.make_node("Gemm", ["flat", "fc_w", "fc_b"], ["logits"], transB=1),
        helper.make_node("Einsum", ["fc_w", "features"], ["cams"], equation="ck,nkhw->nchw"),
    ]
    graph = helper.make_graph(
        nodes,
        "tiny_cropdoc",
        [helper.make_tensor_value_info("image", TensorProto.FLOAT, ["N", 3, 224, 224])],
        [
            helper.make_tensor_value_info("logits", TensorProto.FLOAT, ["N", num_classes]),
            helper.make_tensor_value_info("cams", TensorProto.FLOAT, ["N", num_classes, 7, 7]),
        ],
        initializer=[
            numpy_helper.from_array(conv_w, "conv_w"),
            numpy_helper.from_array(fc_w, "fc_w"),
            numpy_helper.from_array(fc_b, "fc_b"),
        ],
    )
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 17)])
    model.ir_version = 8
    onnx.checker.check_model(model)
    onnx.save(model, str(path))


@pytest.fixture(scope="session")
def tiny_model_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    folder = tmp_path_factory.mktemp("model")
    build_tiny_onnx(folder / "model.onnx")
    (folder / "classes.json").write_text(json.dumps({"classes": FIXTURE_CLASSES}))
    (folder / "model_card.json").write_text(
        json.dumps({"model_version": "test-fixture", "metrics": {"note": "test fixture, not a real result"}})
    )
    (folder / "calibration.json").write_text(
        json.dumps(
            {
                "temperature": 1.0,
                "thresholds": {
                    "min_confidence": 0.0,
                    "max_energy": None,
                    "provisional": True,
                    "source": "test",
                },
            }
        )
    )
    return folder


@pytest.fixture
def diseases_file(tmp_path: Path) -> Path:
    path = tmp_path / "diseases.json"
    path.write_text(
        json.dumps(
            {
                "meta": {"note": "test"},
                "diseases": [
                    {
                        "id": c["id"],
                        "crop": c["crop"],
                        "disease": c["disease"],
                        "category": "healthy" if c["healthy"] else "fungal",
                        "description": f"{c['disease']} description",
                        "general_management": ["Remove infected leaves.", "Avoid overhead watering."],
                        "needs_review": True,
                    }
                    for c in FIXTURE_CLASSES
                ],
            }
        )
    )
    return path


@pytest.fixture
def make_client(tmp_path: Path, diseases_file: Path) -> Iterator[Callable[..., TestClient]]:
    """Factory: ``make_client(model_dir=..., **settings_overrides)`` → TestClient with lifespan."""
    clients: list[TestClient] = []

    def factory(model_dir: Path | None = None, **overrides) -> TestClient:
        settings = Settings(
            model_dir=model_dir or tmp_path / "no-model",
            results_dir=overrides.pop("results_dir", tmp_path / "results"),
            data_dir=tmp_path / "app-data",
            inbox_dir=tmp_path / "inbox",
            frontend_dist=overrides.pop("frontend_dist", tmp_path / "no-dist"),
            diseases_file=diseases_file,
            rate_limit_per_minute=overrides.pop("rate_limit_per_minute", 1000),
            **overrides,
        )
        client = TestClient(create_app(settings))
        client.__enter__()
        clients.append(client)
        return client

    yield factory
    for client in clients:
        client.__exit__(None, None, None)


def image_bytes(
    fmt: str = "JPEG", size: tuple[int, int] = (300, 260), color=(60, 140, 60), **save_kwargs
) -> bytes:
    """Encode a simple synthetic leaf-coloured image."""
    mode = "RGBA" if fmt == "PNG" and save_kwargs.pop("alpha", False) else "RGB"
    image = Image.new(mode, size, color + ((128,) if mode == "RGBA" else ()))
    for x in range(0, size[0], 20):  # some texture so the image is not flat
        image.paste((200, 180, 40) + ((255,) if mode == "RGBA" else ()), (x, 0, x + 5, size[1]))
    buffer = io.BytesIO()
    image.save(buffer, format=fmt, **save_kwargs)
    return buffer.getvalue()
