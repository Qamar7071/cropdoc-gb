"""Build the manifest, duplicate groups and both splits (``make split``).

Outputs
-------
ml/splits/group_aware.csv.gz, ml/splits/naive.csv.gz   committed split files
ml/splits/manifest.json                                SHA256 of each split + parameters + data commit
results/data_audit/*.json                              class counts, detector scores, group stats,
                                                       leakage exposure of the naive split
"""

from __future__ import annotations

import argparse
import gzip
import json
from collections import Counter

import numpy as np
import pandas as pd

from cropdoc import paths
from cropdoc.data import dedup
from cropdoc.data.manifest import absolute, build_manifest
from cropdoc.data.split import (
    group_aware_split,
    groups_crossing_splits,
    naive_split,
    split_csv_bytes,
    split_sha256,
    summarize,
)
from cropdoc.embeddings import compute_embeddings, l2_normalize
from cropdoc.utils import get_logger, read_json, timer, write_json

log = get_logger("cropdoc.split")
AUDIT = paths.RESULTS / "data_audit"
PHASH_BINS = np.arange(0, 66)  # distances 0..64
EXACT_COPY_DISTANCE = 0  # identical pHash under rotation/flip; distance 2 already chains different leaves (D11)
SIM_BINS = np.round(np.arange(-1.0, 1.0001, 0.0025), 4)


def choose_threshold(curve: list[dict], edges: np.ndarray, min_precision: float, link_if_low: bool) -> dict:
    """Pick the threshold with the highest recall whose precision is still ≥ ``min_precision``."""
    ok = [row for row in curve if row["precision"] >= min_precision and row["true_links"] > 0]
    if not ok:
        return {"threshold": None, "precision": None, "recall": 0.0}
    best = max(ok, key=lambda r: (r["recall"], r["precision"]))
    threshold = float(edges[best["bin"]]) if link_if_low else float(edges[best["bin"]])
    return {"threshold": threshold, "precision": best["precision"], "recall": best["recall"], "bin": best["bin"]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--phash-min-precision", type=float, default=0.98)
    parser.add_argument("--embed-min-precision", type=float, default=0.90)
    parser.add_argument("--arch", default="mobilenetv3_large_100")
    parser.add_argument("--no-embeddings", action="store_true", help="pHash + leaf map only")
    parser.add_argument("--manifest-only", action="store_true", help="only write ml/cache/manifest.csv (Colab)")
    args = parser.parse_args(argv)

    with timer("manifest", log):
        manifest = build_manifest()
    paths.CACHE.mkdir(parents=True, exist_ok=True)
    manifest.to_csv(paths.CACHE / "manifest.csv", index=False)
    if args.manifest_only:
        log.info("manifest written (%d photos); committed splits are used as they are", len(manifest))
        return 0
    n = len(manifest)
    log.info("%d images, %d classes, %d mapped by leaf-map", n, manifest.class_id.nunique(), (manifest.leaf_id != "").sum())

    with timer("dihedral pHash", log):
        hash_cache = paths.CACHE / "phash_dihedral.npy"
        if hash_cache.exists() and len(np.load(hash_cache)) == n:
            hashes = np.load(hash_cache)
        else:
            hashes = dedup.hash_files([absolute(p) for p in manifest.path])
            np.save(hash_cache, hashes)

    embeddings = None
    if not args.no_embeddings:
        with timer("embeddings", log):
            embeddings = l2_normalize(compute_embeddings(manifest, args.arch))

    # ---- score detectors against the official leaf map (classes that have mapped photos)
    leaf_ids = manifest.leaf_id.to_numpy()
    phash_same = np.zeros(len(PHASH_BINS) - 1, int)
    phash_diff = np.zeros_like(phash_same)
    sim_same = np.zeros(len(SIM_BINS) - 1, int)
    sim_diff = np.zeros_like(sim_same)
    per_class_index = {c: np.flatnonzero(manifest.class_id.to_numpy() == c) for c in sorted(manifest.class_id.unique())}
    with timer("pairwise scoring vs leaf map", log):
        for idx in per_class_index.values():
            if (leaf_ids[idx] != "").sum() < 2:
                continue
            d = dedup.hamming_min_dihedral(hashes[idx], hashes[idx])
            s, t = dedup.pair_histograms(d, leaf_ids[idx], PHASH_BINS)
            phash_same += s
            phash_diff += t
            if embeddings is not None:
                sim = embeddings[idx] @ embeddings[idx].T
                s, t = dedup.pair_histograms(sim, leaf_ids[idx], SIM_BINS)
                sim_same += s
                sim_diff += t
    phash_curve = dedup.precision_recall_curve(phash_same, phash_diff, link_if_low=True)
    phash_choice = choose_threshold(phash_curve, PHASH_BINS, args.phash_min_precision, link_if_low=True)
    sim_curve, sim_choice = [], {"threshold": None}
    if embeddings is not None:
        sim_curve = dedup.precision_recall_curve(sim_same, sim_diff, link_if_low=False)
        sim_choice = choose_threshold(sim_curve, SIM_BINS, args.embed_min_precision, link_if_low=False)
    log.info("pHash threshold %s | embedding threshold %s", phash_choice, sim_choice)

    # ---- build groups: leaf map ∪ pHash ∪ embeddings (within class)
    uf = dedup.UnionFind(n)
    first_of_leaf: dict[str, int] = {}
    for i, leaf in enumerate(leaf_ids):
        if leaf:
            uf.union(i, first_of_leaf.setdefault(leaf, i))
    edge_counts = Counter()
    # near-exact copies (≤ EXACT_COPY_DISTANCE bits apart under rotation/flip) are always linked:
    # a copied photo is leakage whatever the leaf map says
    phash_link = max(phash_choice["threshold"] or 0, EXACT_COPY_DISTANCE)
    with timer("linking duplicates", log):
        for idx in per_class_index.values():
            d = dedup.hamming_min_dihedral(hashes[idx], hashes[idx])
            pairs = dedup.pairs_below(d, phash_link, link_if_low=True)
            edge_counts["phash"] += len(pairs)
            uf.union_pairs(idx[pairs])
            if embeddings is not None and sim_choice["threshold"] is not None:
                sim = embeddings[idx] @ embeddings[idx].T
                pairs = dedup.pairs_below(sim, sim_choice["threshold"], link_if_low=False)
                edge_counts["embedding"] += len(pairs)
                uf.union_pairs(idx[pairs])
    groups = uf.labels()
    manifest["group"] = groups

    # ---- exact copies across classes (possible label errors): identical canonical pHash
    canonical = hashes.min(axis=1)
    by_hash = pd.DataFrame({"h": canonical, "class_id": manifest.class_id, "path": manifest.path})
    multi = by_hash.groupby("h")["class_id"].nunique()
    cross = by_hash[by_hash.h.isin(multi[multi > 1].index)].sort_values("h")

    # ---- splits
    labels = manifest.label.to_numpy()
    manifest["split_group"] = group_aware_split(labels, groups, seed=args.seed)
    manifest["split_naive"] = naive_split(labels, seed=args.seed)
    crossing = groups_crossing_splits(groups, manifest.split_group.to_numpy())
    if crossing:
        raise RuntimeError(f"{crossing} groups cross splits in the group-aware split")

    # leakage exposure of the naive split: test photos that have a same-group sibling in train
    naive_train_groups = set(groups[manifest.split_naive.to_numpy() == "train"])
    naive_test = manifest.split_naive.to_numpy() == "test"
    exposed = np.array([g in naive_train_groups for g in groups[naive_test]])

    paths.SPLITS.mkdir(parents=True, exist_ok=True)
    cols = ["path", "class_id", "label", "group"]
    split_info = {}
    for name, col in (("group_aware", "split_group"), ("naive", "split_naive")):
        frame = manifest[cols + [col]].rename(columns={col: "split"})
        data = split_csv_bytes(frame)
        with gzip.GzipFile(paths.SPLITS / f"{name}.csv.gz", "wb", mtime=0) as fh:
            fh.write(data)
        split_info[name] = {"file": f"ml/splits/{name}.csv.gz", "sha256_csv": split_sha256(frame), **summarize(frame)}

    sources = read_json(paths.RAW / "SOURCES.json") if (paths.RAW / "SOURCES.json").exists() else {}
    sizes = Counter(groups)
    size_hist = Counter(sizes.values())
    group_stats = {
        "n_images": n,
        "n_groups": len(sizes),
        "images_in_multi_photo_groups": int(sum(v for v in sizes.values() if v > 1)),
        "largest_group": int(max(sizes.values())),
        "group_size_histogram": {str(k): int(v) for k, v in sorted(size_hist.items())},
        "edges": {"leaf_map_images": int((leaf_ids != "").sum()), **{k: int(v) for k, v in edge_counts.items()}},
    }
    write_json(
        paths.SPLITS / "manifest.json",
        {
            "seed": args.seed,
            "proportions": {"train": 0.70, "val": 0.15, "test": 0.15},
            "method": "StratifiedGroupKFold(20 folds): 3 test, 3 val, 14 train; groups = leaf-map ∪ pHash ∪ embeddings",
            "thresholds": {"phash_max_distance": phash_link, "phash_calibrated": phash_choice["threshold"],
                           "embedding_min_cosine": sim_choice["threshold"]},
            "embedding_arch": None if args.no_embeddings else args.arch,
            "data_sources": sources,
            "splits": split_info,
            "groups_crossing_splits": {"group_aware": crossing,
                                       "naive": groups_crossing_splits(groups, manifest.split_naive.to_numpy())},
        },
    )
    write_json(AUDIT / "group_stats.json", group_stats)
    write_json(
        AUDIT / "dedup_calibration.json",
        {
            "ground_truth": "PlantVillage leaf-map.json (pairs of mapped photos within a class)",
            "phash": {"choice": phash_choice, "min_precision": args.phash_min_precision,
                      "curve": [dict(r, threshold=int(PHASH_BINS[r["bin"]])) for r in phash_curve[:25]]},
            "embedding": {"choice": sim_choice, "min_precision": args.embed_min_precision, "arch": args.arch,
                          "curve": [dict(r, threshold=float(SIM_BINS[r["bin"]])) for r in sim_curve[::8]]},
        },
    )
    write_json(
        AUDIT / "naive_split_exposure.json",
        {
            "description": "Naive split: share of test photos whose duplicate group also has photos in train",
            "test_images": int(naive_test.sum()),
            "exposed_test_images": int(exposed.sum()),
            "exposed_fraction": float(exposed.mean()),
        },
    )
    counts = manifest.groupby("class_id").size()
    write_json(
        AUDIT / "class_counts.json",
        {"counts": {k: int(v) for k, v in counts.items()}, "min": int(counts.min()), "max": int(counts.max()),
         "imbalance_ratio": float(counts.max() / counts.min())},
    )
    write_json(
        AUDIT / "cross_class_duplicates.json",
        {"description": "Photos with identical (rotation/flip-invariant) pHash in different classes",
         "n_images": int(len(cross)), "examples": cross.head(40)[["class_id", "path"]].to_dict("records")},
    )
    log.info("groups=%d largest=%d | naive exposure=%.3f | written to %s", len(sizes), group_stats["largest_group"],
             float(exposed.mean()), paths.SPLITS)
    print(json.dumps({"group_stats": group_stats, "phash": phash_choice, "embedding": sim_choice}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
