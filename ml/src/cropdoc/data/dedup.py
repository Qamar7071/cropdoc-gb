"""Find photos of the same physical leaf, so they never end up in different splits.

Intuition
---------
PlantVillage often has several photos of one leaf (turned, flipped, re-shot). If one photo is in
training and its twin is in the test set, the test becomes an open-book exam and accuracy looks
better than it really is ("leakage"). We link photos that are probably the same leaf and put
each linked *group* entirely in one split.

Three kinds of links (edges):
1. the official ``leaf-map.json`` (ground truth for ~75% of photos);
2. **perceptual hash (pHash)**: a 64-bit fingerprint of the image's coarse structure. We compute it
   for all 8 rotations/flips, so a rotated copy still matches. Small Hamming distance → near-copy;
3. **embedding similarity**: cosine similarity of pretrained CNN features, which catches re-shot
   photos that pHash misses.
The pHash/embedding thresholds are chosen by scoring them against the leaf map (precision/recall).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.fft import dctn

HASH_IMAGE_SIZE = 32  # 32×32 grayscale, keep the 8×8 lowest DCT frequencies (standard pHash)
HASH_SIZE = 8


# ----------------------------------------------------------------------------- perceptual hash
def dihedral_variants(gray: np.ndarray) -> np.ndarray:
    """The 8 rotations/flips of a square array, stacked on a new first axis."""
    variants = [np.rot90(gray, k) for k in range(4)]
    variants += [np.fliplr(v) for v in variants]
    return np.stack(variants)


def phash_bits(gray32: np.ndarray) -> np.ndarray:
    """pHash of one or many 32×32 arrays: DCT → top-left 8×8 → bit = coefficient > median."""
    coeffs = dctn(gray32.astype(np.float64), type=2, axes=(-2, -1), norm="ortho")
    low = coeffs[..., :HASH_SIZE, :HASH_SIZE].reshape(*gray32.shape[:-2], HASH_SIZE * HASH_SIZE)
    median = np.median(low, axis=-1, keepdims=True)
    return low > median


def pack_bits(bits: np.ndarray) -> np.ndarray:
    """(..., 64) booleans → (...,) uint64."""
    weights = (np.uint64(1) << np.arange(64, dtype=np.uint64)).astype(np.uint64)
    return (bits.astype(np.uint64) * weights).sum(axis=-1, dtype=np.uint64)


def dihedral_phash(image: Image.Image) -> np.ndarray:
    """8 pHashes (uint64) for the 8 rotations/flips of one image."""
    gray = np.asarray(
        image.convert("L").resize((HASH_IMAGE_SIZE, HASH_IMAGE_SIZE), Image.Resampling.LANCZOS),
        dtype=np.float64,
    )
    return pack_bits(phash_bits(dihedral_variants(gray)))


def hash_files(files: Sequence[Path], workers: int = 4) -> np.ndarray:
    """Dihedral pHashes for many files → (N, 8) uint64 (parallel image decoding)."""

    def one(path: Path) -> np.ndarray:
        with Image.open(path) as image:
            return dihedral_phash(image)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        return np.stack(list(pool.map(one, files, chunksize=64)))


def hamming_min_dihedral(hashes_a: np.ndarray, hashes_b: np.ndarray) -> np.ndarray:
    """Distance matrix d[i, j] = min over the 8 variants t of popcount(a[i, 0] XOR b[j, t])."""
    base = hashes_a[:, 0][:, None]
    best = np.full((len(hashes_a), len(hashes_b)), 64, dtype=np.uint8)
    for t in range(hashes_b.shape[1]):
        np.minimum(best, np.bitwise_count(base ^ hashes_b[:, t][None, :]).astype(np.uint8), out=best)
    return best


# ----------------------------------------------------------------------------- union-find
class UnionFind:
    """Disjoint sets: union(a, b) links two items; find(a) returns the group representative."""

    def __init__(self, n: int):
        self.parent = np.arange(n)

    def find(self, a: int) -> int:
        root = a
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[a] != root:  # path compression
            self.parent[a], a = root, self.parent[a]
        return int(root)

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[max(ra, rb)] = min(ra, rb)

    def union_pairs(self, pairs: Iterable[tuple[int, int]]) -> None:
        for a, b in pairs:
            self.union(int(a), int(b))

    def labels(self) -> np.ndarray:
        """Group label per item (the smallest member index of each group)."""
        return np.array([self.find(i) for i in range(len(self.parent))])


# ----------------------------------------------------------------------------- scoring vs ground truth
def pair_histograms(
    score_matrix: np.ndarray, truth_ids: np.ndarray, bins: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Histogram of a pairwise score for same-leaf vs different-leaf pairs (upper triangle only).

    ``truth_ids`` holds the leaf id per item ("" = unknown; unknown items are ignored).
    """
    known = truth_ids != ""
    idx = np.flatnonzero(known)
    if len(idx) < 2:
        return np.zeros(len(bins) - 1, int), np.zeros(len(bins) - 1, int)
    sub = score_matrix[np.ix_(idx, idx)]
    same = truth_ids[idx][:, None] == truth_ids[idx][None, :]
    upper = np.triu(np.ones_like(same, dtype=bool), k=1)
    same_hist, _ = np.histogram(sub[upper & same], bins=bins)
    diff_hist, _ = np.histogram(sub[upper & ~same], bins=bins)
    return same_hist, diff_hist


def precision_recall_curve(
    same_hist: np.ndarray, diff_hist: np.ndarray, link_if_low: bool
) -> list[dict[str, float]]:
    """Precision/recall of "link the pair" for every threshold (bin edge).

    ``link_if_low=True`` for distances (link when distance ≤ threshold),
    ``False`` for similarities (link when similarity ≥ threshold).
    """
    if link_if_low:
        tp, fp = np.cumsum(same_hist), np.cumsum(diff_hist)
    else:
        tp, fp = np.cumsum(same_hist[::-1])[::-1], np.cumsum(diff_hist[::-1])[::-1]
    total_same = same_hist.sum()
    rows = []
    for i in range(len(same_hist)):
        linked = tp[i] + fp[i]
        rows.append(
            {
                "bin": i,
                "true_links": int(tp[i]),
                "false_links": int(fp[i]),
                "precision": float(tp[i] / linked) if linked else 1.0,
                "recall": float(tp[i] / total_same) if total_same else 0.0,
            }
        )
    return rows


def pairs_below(matrix: np.ndarray, threshold: float, link_if_low: bool) -> np.ndarray:
    """Index pairs (i < j) whose score passes the threshold."""
    mask = matrix <= threshold if link_if_low else matrix >= threshold
    i, j = np.nonzero(np.triu(mask, k=1))
    return np.stack([i, j], axis=1)
