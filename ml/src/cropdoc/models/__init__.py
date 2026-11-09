"""Model zoo: every model ends in global-average-pool → dropout → linear (CAM-friendly head).

Why that head? With it, Grad-CAM equals the simpler CAM exactly, so the exported ONNX model can
output heatmaps directly and the web app never needs PyTorch (tested in ml/tests/test_models.py).
"""

from __future__ import annotations

from cropdoc.models.camnet import CamNet, build_model

__all__ = ["CamNet", "build_model"]
