"""Baselines that make the deep-learning gains meaningful (``make baseline``).

* **Classical:** hand-made features (colour histogram in HSV + edge-direction histogram + simple
  texture statistics) fed to logistic regression and a random forest.
* **Tiny MLP (an "ANN"):** a 2-hidden-layer neural network on raw 32×32 pixels, with no convolutions.
* **1-nearest-neighbour** on pretrained CNN features: copies the label of the most similar training
  photo. It is the perfect "leakage detector", because under a naive split the nearest photo is often
  the same leaf.
Every baseline is run on both the naive and the group-aware split (3 seeds where randomness matters).
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd
import torch
from PIL import Image
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score
from sklearn.preprocessing import StandardScaler

from cropdoc import paths
from cropdoc.data.manifest import absolute
from cropdoc.utils import get_logger, seed_everything

log = get_logger("cropdoc.baselines")
SEEDS = [0, 1, 2]


def _image_features(path: str) -> tuple[np.ndarray, np.ndarray]:
    """(hand-made feature vector, 32×32×3 uint8 pixels) for one photo."""
    with Image.open(absolute(path)) as image:
        rgb = image.convert("RGB")
    small = np.asarray(rgb.resize((64, 64), Image.Resampling.BILINEAR))
    pixels = np.asarray(rgb.resize((32, 32), Image.Resampling.BILINEAR), dtype=np.uint8)
    hsv = np.asarray(Image.fromarray(small).convert("HSV"), dtype=np.float32)
    colour = np.concatenate(
        [np.histogram(hsv[..., c], bins=16, range=(0, 255), density=True)[0] for c in range(3)]
    )
    gray = np.asarray(Image.fromarray(small).convert("L"), dtype=np.float32) / 255.0
    gy, gx = np.gradient(gray)
    magnitude, angle = np.hypot(gx, gy), np.arctan2(gy, gx)
    edges = np.histogram(angle, bins=12, range=(-np.pi, np.pi), weights=magnitude)[0]
    edges = edges / (edges.sum() + 1e-8)
    texture = np.array([gray.mean(), gray.std(), magnitude.mean(), magnitude.std(), (magnitude > 0.1).mean()])
    return np.concatenate([colour, edges, texture]).astype(np.float32), pixels


def load_features(frame: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Hand-made features and 32×32 pixels for every row (cached)."""
    cache = paths.CACHE / "baseline_features.npz"
    if cache.exists():
        stored = np.load(cache, allow_pickle=True)
        if len(stored["paths"]) == len(frame) and (stored["paths"] == frame.path.to_numpy()).all():
            return stored["features"], stored["pixels"]
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(_image_features, frame.path, chunksize=128))
    features = np.stack([r[0] for r in results])
    pixels = np.stack([r[1] for r in results])
    np.savez_compressed(cache, features=features, pixels=pixels, paths=frame.path.to_numpy())
    return features, pixels


def _scores(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "macro_f1": float(f1_score(y_true, y_pred, average="macro")),
    }


def logistic_regression(x_tr, y_tr, x_te, y_te, seed: int) -> dict:
    scaler = StandardScaler().fit(x_tr)
    model = LogisticRegression(max_iter=2000, C=1.0, random_state=seed)
    model.fit(scaler.transform(x_tr), y_tr)
    return _scores(y_te, model.predict(scaler.transform(x_te)))


def random_forest(x_tr, y_tr, x_te, y_te, seed: int) -> dict:
    model = RandomForestClassifier(n_estimators=200, n_jobs=4, random_state=seed, min_samples_leaf=2)
    model.fit(x_tr, y_tr)
    return _scores(y_te, model.predict(x_te))


def tiny_mlp(x_tr, y_tr, x_te, y_te, seed: int, epochs: int = 15) -> dict:
    """3072 → 512 → 256 → 38 fully-connected network on standardized pixels (CPU, ~1 min)."""
    seed_everything(seed)
    mean, std = x_tr.mean(0), x_tr.std(0) + 1e-6
    xt = torch.from_numpy(((x_tr - mean) / std).astype(np.float32))
    xv = torch.from_numpy(((x_te - mean) / std).astype(np.float32))
    yt = torch.from_numpy(y_tr).long()
    model = torch.nn.Sequential(
        torch.nn.Linear(xt.shape[1], 512),
        torch.nn.ReLU(),
        torch.nn.Dropout(0.3),
        torch.nn.Linear(512, 256),
        torch.nn.ReLU(),
        torch.nn.Dropout(0.3),
        torch.nn.Linear(256, int(y_tr.max()) + 1),
    )
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
    generator = torch.Generator().manual_seed(seed)
    for _ in range(epochs):
        model.train()
        for idx in torch.randperm(len(xt), generator=generator).split(256):
            loss = torch.nn.functional.cross_entropy(model(xt[idx]), yt[idx])
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
    model.eval()
    with torch.no_grad():
        preds = torch.cat([model(chunk).argmax(1) for chunk in xv.split(4096)]).numpy()
    return _scores(y_te, preds)


def nearest_neighbour(x_tr, y_tr, x_te, y_te, seed: int = 0) -> dict:
    """1-NN by cosine similarity (deterministic; ``seed`` unused)."""
    a = x_tr / (np.linalg.norm(x_tr, axis=1, keepdims=True) + 1e-12)
    b = x_te / (np.linalg.norm(x_te, axis=1, keepdims=True) + 1e-12)
    preds = np.concatenate(
        [y_tr[(chunk @ a.T).argmax(1)] for chunk in np.array_split(b, max(1, len(b) // 1024))]
    )
    return _scores(y_te, preds)
