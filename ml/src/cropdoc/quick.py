"""Quick model: a real, CPU-trainable model so the app works end to end (Milestone 1).

Recipe (transfer learning, intuition first)
-------------------------------------------
1. **Frozen backbone (linear probe).** An ImageNet-pretrained MobileNetV3 already "knows" edges,
   textures and shapes. We keep it frozen, compute one feature vector per photo, and train only a
   linear layer on top. Fast, because features are computed once.
2. **Brief fine-tune.** Unfreeze the last blocks and train a little on augmented photos (random
   crops, flips, colour changes), so the deeper features adapt to leaves.
3. **Model selection on validation**, then **temperature scaling** and the "not sure" thresholds,
   also on validation. The test split is used once, at the end, for the numbers in model_card.json.
"""

from __future__ import annotations

import gzip
import io
import math
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import accuracy_score, classification_report, f1_score
from torch import nn
from torch.utils.data import DataLoader

from cropdoc import paths
from cropdoc.data.classes import CLASS_IDS
from cropdoc.data.datasets import ManifestDataset
from cropdoc.data.transforms import eval_transform, train_transform
from cropdoc.models import CamNet, build_model
from cropdoc.models.camnet import OnnxCamWrapper
from cropdoc.utils import get_logger, worker_init_fn

log = get_logger("cropdoc.quick")


# ----------------------------------------------------------------------------- data helpers
def load_split(name: str = "group_aware") -> pd.DataFrame:
    """Read a committed split file (path, class_id, label, group, split)."""
    with gzip.open(paths.SPLITS / f"{name}.csv.gz", "rb") as fh:
        return pd.read_csv(io.BytesIO(fh.read()))


def balanced_subset(frame: pd.DataFrame, per_class: int, seed: int) -> pd.DataFrame:
    """At most ``per_class`` random rows of each class (all rows for small classes)."""
    parts = [g.sample(min(len(g), per_class), random_state=seed) for _, g in frame.groupby("label")]
    return pd.concat(parts).sample(frac=1.0, random_state=seed).reset_index(drop=True)


def classification_metrics(labels: np.ndarray, preds: np.ndarray) -> dict:
    """Accuracy, macro-F1 (every class counts equally) and weighted-F1."""
    return {
        "n": int(len(labels)),
        "accuracy": float(accuracy_score(labels, preds)),
        "macro_f1": float(f1_score(labels, preds, average="macro")),
        "weighted_f1": float(f1_score(labels, preds, average="weighted")),
    }


def per_class_table(labels: np.ndarray, preds: np.ndarray) -> pd.DataFrame:
    """Precision/recall/F1/support per class."""
    report = classification_report(
        labels,
        preds,
        labels=list(range(len(CLASS_IDS))),
        target_names=CLASS_IDS,
        output_dict=True,
        zero_division=0,
    )
    rows = [
        {"class_id": c, **{k: report[c][k] for k in ("precision", "recall", "f1-score", "support")}}
        for c in CLASS_IDS
    ]
    return pd.DataFrame(rows).rename(columns={"f1-score": "f1"})


# ----------------------------------------------------------------------------- stage 1: linear probe
@dataclass
class ProbeResult:
    weight: np.ndarray
    bias: np.ndarray
    val_metrics: dict
    epochs: int


def train_linear_probe(
    x_train: np.ndarray,
    y_train: np.ndarray,
    x_val: np.ndarray,
    y_val: np.ndarray,
    num_classes: int,
    seed: int = 42,
    epochs: int = 60,
    patience: int = 8,
    lr: float = 2e-3,
    weight_decay: float = 1e-4,
    batch_size: int = 512,
) -> ProbeResult:
    """Multinomial logistic regression (a linear layer) trained with AdamW + early stopping on val macro-F1."""
    torch.manual_seed(seed)
    layer = nn.Linear(x_train.shape[1], num_classes)
    optimizer = torch.optim.AdamW(layer.parameters(), lr=lr, weight_decay=weight_decay)
    xt, yt = torch.from_numpy(x_train), torch.from_numpy(y_train).long()
    xv = torch.from_numpy(x_val)
    generator = torch.Generator().manual_seed(seed)
    best = (-1.0, None, 0)
    stale = 0
    for epoch in range(1, epochs + 1):
        layer.train()
        for idx in torch.randperm(len(xt), generator=generator).split(batch_size):
            loss = nn.functional.cross_entropy(layer(xt[idx]), yt[idx])
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
        layer.eval()
        with torch.no_grad():
            preds = layer(xv).argmax(1).numpy()
        score = f1_score(y_val, preds, average="macro")
        if score > best[0] + 1e-5:
            best = (score, {k: v.clone() for k, v in layer.state_dict().items()}, epoch)
            stale = 0
        else:
            stale += 1
            if stale >= patience:
                break
    layer.load_state_dict(best[1])
    with torch.no_grad():
        preds = layer(xv).argmax(1).numpy()
    return ProbeResult(
        weight=layer.weight.detach().numpy().copy(),
        bias=layer.bias.detach().numpy().copy(),
        val_metrics=classification_metrics(y_val, preds),
        epochs=best[2],
    )


# ----------------------------------------------------------------------------- inference helpers
def torch_logits(model: CamNet, frame: pd.DataFrame, batch_size: int = 64, workers: int = 3) -> np.ndarray:
    """Logits for every row (deterministic eval transform)."""
    model.eval()
    loader = DataLoader(ManifestDataset(frame, eval_transform()), batch_size=batch_size, num_workers=workers)
    outputs = []
    with torch.inference_mode():
        for images, _, _ in loader:
            outputs.append(model(images.contiguous(memory_format=torch.channels_last)).float().numpy())
    return np.concatenate(outputs)


def onnx_outputs(onnx_path: Path, frame: pd.DataFrame, batch_size: int = 64, workers: int = 3) -> np.ndarray:
    """Logits from the exported ONNX model (the exact artifact the web app uses)."""
    import onnxruntime as ort

    session = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    loader = DataLoader(ManifestDataset(frame, eval_transform()), batch_size=batch_size, num_workers=workers)
    return np.concatenate([session.run(["logits"], {"image": images.numpy()})[0] for images, _, _ in loader])


def export_onnx(model: CamNet, path: Path) -> Path:
    """Export (logits, cams) with a dynamic batch dimension, then verify parity with PyTorch."""
    from cropdoc.export import export_and_verify

    model = model.eval().to(memory_format=torch.contiguous_format)
    return export_and_verify(OnnxCamWrapper(model), path, output_names=["logits", "cams"])


# ----------------------------------------------------------------------------- stage 2: brief fine-tune
def _freeze_batchnorm_of_frozen_layers(model: nn.Module) -> None:
    """BatchNorm layers whose weights are frozen also keep their running statistics fixed."""
    for module in model.modules():
        if isinstance(module, nn.BatchNorm2d) and not any(p.requires_grad for p in module.parameters()):
            module.eval()


def finetune_tail(
    model: CamNet,
    train_frame: pd.DataFrame,
    val_frame: pd.DataFrame,
    epochs: int = 3,
    tail_blocks: int = 3,
    batch_size: int = 32,
    lr_tail: float = 3e-4,
    lr_head: float = 1e-3,
    seed: int = 42,
    workers: int = 3,
    max_minutes: float | None = None,
) -> tuple[CamNet, list[dict]]:
    """Fine-tune the last ``tail_blocks`` blocks + head with standard augmentation; keep the best epoch."""
    model.freeze_backbone(trainable_tail_blocks=tail_blocks)
    model.to(memory_format=torch.channels_last)
    tail = [p for p in model.backbone.parameters() if p.requires_grad]
    optimizer = torch.optim.AdamW(
        [{"params": tail, "lr": lr_tail}, {"params": model.fc.parameters(), "lr": lr_head}], weight_decay=1e-4
    )
    generator = torch.Generator().manual_seed(seed)
    loader = DataLoader(
        ManifestDataset(train_frame, train_transform("standard")),
        batch_size=batch_size,
        shuffle=True,
        num_workers=workers,
        worker_init_fn=worker_init_fn,
        generator=generator,
        drop_last=True,
        persistent_workers=True,
    )
    total_steps = epochs * len(loader)
    warmup = min(50, total_steps // 10)
    schedule = torch.optim.lr_scheduler.LambdaLR(
        optimizer,
        lambda step: (
            (step + 1) / warmup
            if step < warmup
            else 0.5 * (1 + math.cos(math.pi * (step - warmup) / max(1, total_steps - warmup)))
        ),
    )
    y_val = val_frame["label"].to_numpy()
    best_score, best_state, history = -1.0, None, []
    start = time.time()
    for epoch in range(1, epochs + 1):
        model.train()
        _freeze_batchnorm_of_frozen_layers(model)
        running, seen = 0.0, 0
        for step, (images, labels, _) in enumerate(loader):
            logits = model(images.contiguous(memory_format=torch.channels_last))
            loss = nn.functional.cross_entropy(logits, labels)
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            schedule.step()
            running += loss.item() * len(labels)
            seen += len(labels)
            if step % 50 == 0:
                log.info(
                    "epoch %d step %d/%d loss %.4f (%.0f img/s)",
                    epoch,
                    step,
                    len(loader),
                    running / seen,
                    seen / max(1e-6, time.time() - start - sum(h["seconds"] for h in history)),
                )
        val_preds = torch_logits(model, val_frame, workers=workers).argmax(1)
        metrics = classification_metrics(y_val, val_preds)
        elapsed = time.time() - start
        history.append(
            {
                "epoch": epoch,
                "train_loss": running / seen,
                "seconds": elapsed - sum(h["seconds"] for h in history),
                **{f"val_{k}": v for k, v in metrics.items() if k != "n"},
            }
        )
        log.info("epoch %d: %s", epoch, history[-1])
        if metrics["macro_f1"] > best_score:
            best_score = metrics["macro_f1"]
            best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}
        if max_minutes and elapsed / 60 > max_minutes:
            log.info("time budget reached after epoch %d", epoch)
            break
    model.load_state_dict(best_state)
    return model.eval(), history


def build_stage1_model(probe: ProbeResult, arch: str = "mobilenetv3_large_100") -> CamNet:
    """Pretrained backbone + linear head copied from the probe."""
    model = build_model(arch, num_classes=len(probe.bias), pretrained=True)
    with torch.no_grad():
        model.fc.weight.copy_(torch.from_numpy(probe.weight))
        model.fc.bias.copy_(torch.from_numpy(probe.bias))
    return model.eval()
