"""Unit tests for small backend helpers (no HTTP)."""

from __future__ import annotations

import numpy as np
from PIL import Image

from app.ratelimit import TokenBucket
from app.services.gradcam import colormap, heatmap_image, normalize_cam
from app.services.ood import (
    CONFIDENT,
    LOW_CONFIDENCE,
    UNSUPPORTED,
    Thresholds,
    decide_status,
    energy_score,
    softmax,
)
from app.services.preprocess import center_crop, preprocess, resize_shorter_side


def test_softmax_handles_masked_classes():
    probs = softmax(np.array([2.0, -np.inf, 0.0]))
    assert probs[1] == 0.0 and abs(probs.sum() - 1) < 1e-12


def test_energy_is_higher_for_flat_small_logits():
    confident = energy_score(np.array([[10.0, 0.0, 0.0]]))
    flat = energy_score(np.array([[0.1, 0.1, 0.1]]))
    assert flat[0] > confident[0]


def test_decide_status_order():
    thresholds = Thresholds(min_confidence=0.6, max_energy=-2.0)
    assert decide_status(0.9, -5.0, thresholds) == CONFIDENT
    assert decide_status(0.4, -5.0, thresholds) == LOW_CONFIDENCE
    assert decide_status(0.9, -1.0, thresholds) == UNSUPPORTED  # unsupported wins


def test_resize_and_crop_match_torchvision_rounding():
    image = Image.new("RGB", (500, 300))
    resized = resize_shorter_side(image, 256)
    assert resized.size == (426, 256)  # int(256 * 500 / 300) = 426
    assert center_crop(resized, 224).size == (224, 224)
    array, crop = preprocess(image)
    assert array.shape == (1, 3, 224, 224) and array.dtype == np.float32 and crop.size == (224, 224)


def test_cam_normalization_and_colormap():
    cam = np.array([[-1.0, 0.0], [1.0, 3.0]])
    norm = normalize_cam(cam)
    assert norm.min() == 0.0 and norm.max() == 1.0
    assert colormap(np.array([0.0]))[0].tolist() == [0, 0, 127]  # dark blue at 0 (jet)
    assert colormap(np.array([1.0]))[0].tolist() == [127, 0, 0]  # dark red at 1
    assert colormap(np.array([0.5]))[0].tolist()[1] == 255  # green-ish in the middle
    assert heatmap_image(cam, (10, 10)).size == (10, 10)


def test_token_bucket_refills():
    bucket = TokenBucket(capacity=2, refill_per_second=1.0)
    assert bucket.allow("ip", now=0.0) and bucket.allow("ip", now=0.0)
    assert not bucket.allow("ip", now=0.0)
    assert bucket.allow("ip", now=1.5)
