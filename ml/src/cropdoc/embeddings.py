"""Pretrained-feature embeddings computed fast on CPU with ONNX Runtime.

The pooled feature vector of an ImageNet-pretrained CNN summarizes an image in ~1000 numbers.
We use it twice: (1) to find near-duplicate photos (cosine similarity), and (2) to train the
quick model's first stage (a linear classifier on frozen features), without recomputing anything.
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from torch import nn
from torch.utils.data import DataLoader

from cropdoc import paths
from cropdoc.data.datasets import ManifestDataset
from cropdoc.data.transforms import eval_transform
from cropdoc.models import build_model
from cropdoc.utils import get_logger, sha256_bytes

log = get_logger("cropdoc.embeddings")


class _Embedder(nn.Module):
    def __init__(self, model: nn.Module):
        super().__init__()
        self.model = model

    def forward(self, image: torch.Tensor) -> torch.Tensor:
        return self.model.embed(image)


def export_embedder(arch: str, path: Path) -> Path:
    """Export ``pretrained backbone + global average pool`` to ONNX (input image → embedding)."""
    if path.exists():
        return path
    from cropdoc.export import export_and_verify

    model = build_model(arch, num_classes=1, pretrained=True).eval()
    return export_and_verify(_Embedder(model), path, output_names=["embedding"])


def compute_embeddings(
    frame: pd.DataFrame, arch: str = "mobilenetv3_large_100", batch_size: int = 64, workers: int = 3
) -> np.ndarray:
    """Raw pooled embeddings for every row of ``frame`` (cached on disk by content hash).

    Raw (not normalized) so a linear head trained on them can be copied into the CNN as-is;
    call ``l2_normalize`` before computing cosine similarities.
    """
    key = sha256_bytes(("\n".join(frame["path"]) + arch).encode())[:16]
    cache = paths.CACHE / "embeddings" / f"{arch}_{key}.npy"
    if cache.exists():
        return np.load(cache)

    import onnxruntime as ort

    onnx_path = export_embedder(arch, paths.CACHE / "embeddings" / f"{arch}_embedder.onnx")
    options = ort.SessionOptions()
    options.intra_op_num_threads = max(1, (os.cpu_count() or 4))
    session = ort.InferenceSession(str(onnx_path), options, providers=["CPUExecutionProvider"])

    loader = DataLoader(
        ManifestDataset(frame.assign(label=0), eval_transform()),
        batch_size=batch_size,
        num_workers=workers,
        shuffle=False,
    )
    chunks = []
    for step, (images, _, _) in enumerate(loader):
        chunks.append(session.run(["embedding"], {"image": images.numpy()})[0])
        if step % 100 == 0:
            log.info("embeddings %d/%d", step * batch_size, len(frame))
    embeddings = np.concatenate(chunks).astype(np.float32)
    cache.parent.mkdir(parents=True, exist_ok=True)
    np.save(cache, embeddings)
    return embeddings


def l2_normalize(embeddings: np.ndarray) -> np.ndarray:
    """Unit-length rows, so a dot product is the cosine similarity."""
    return embeddings / (np.linalg.norm(embeddings, axis=1, keepdims=True) + 1e-12)
