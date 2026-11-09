"""Duplicate-detection tests: rotated/flipped copies match, different images do not."""

from __future__ import annotations

import numpy as np
from PIL import Image

from cropdoc.data.dedup import (
    UnionFind,
    dihedral_phash,
    hamming_min_dihedral,
    pair_histograms,
    precision_recall_curve,
)
from cropdoc.data.manifest import leaf_key_from_filename


def leafish(seed: int, size: int = 128) -> Image.Image:
    rng = np.random.default_rng(seed)
    base = rng.integers(0, 255, size=(8, 8, 3), dtype=np.uint8)
    return Image.fromarray(base).resize((size, size), Image.Resampling.BILINEAR)


def test_rotations_and_flips_are_detected_as_duplicates():
    image = leafish(1)
    variants = [image, image.rotate(90, expand=True), image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)]
    hashes = np.stack([dihedral_phash(v) for v in variants])
    distances = hamming_min_dihedral(hashes, hashes)
    assert distances.max() <= 2  # all three are the same photo up to rotation/flip


def test_different_images_are_far_apart():
    hashes = np.stack([dihedral_phash(leafish(s)) for s in range(6)])
    distances = hamming_min_dihedral(hashes, hashes)
    off_diagonal = distances[~np.eye(6, dtype=bool)]
    assert off_diagonal.min() > 10


def test_union_find_merges_transitively():
    uf = UnionFind(5)
    uf.union_pairs([(0, 1), (1, 2), (3, 4)])
    labels = uf.labels()
    assert labels[0] == labels[1] == labels[2] and labels[3] == labels[4] and labels[0] != labels[3]


def test_precision_recall_against_ground_truth():
    distances = np.array([[0, 1, 30], [1, 0, 30], [30, 30, 0]], dtype=np.uint8)
    leaf_ids = np.array(["a", "a", "b"])
    same, diff = pair_histograms(distances, leaf_ids, np.arange(0, 66))
    curve = precision_recall_curve(same, diff, link_if_low=True)
    assert curve[1]["recall"] == 1.0 and curve[1]["precision"] == 1.0  # threshold 1 links only (0,1)
    assert curve[30]["precision"] == 1 / 3  # threshold 30 also links the two wrong pairs


def test_leaf_key_matches_leaf_map_format():
    assert leaf_key_from_filename("00fc2ee5-729f___RS_HL 1864.JPG") == "rs_hl 1864"
