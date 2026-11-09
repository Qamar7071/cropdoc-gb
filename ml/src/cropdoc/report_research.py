"""Research blocks for README.md / MODEL_CARD.md, generated from results/*.json (registered on import)."""

from __future__ import annotations

from cropdoc import paths
from cropdoc.report import EXTRA_BLOCKS, PENDING, _load, num, pct


def _ci(d: dict, scale: float = 100) -> str:
    return f"{d['estimate'] * scale:.1f} (95% CI {d['ci_low'] * scale:.1f} to {d['ci_high'] * scale:.1f})"


def block_headline_gap() -> str:
    gap = _load("results/shift/plantdoc_gap.json")
    if not gap:
        return f"{PENDING}: run `make shift`."
    lab, field, hint, cal = gap["lab"], gap["field"], gap["field_crop_hint"], gap["calibration"]
    safe_f, safe_l = gap["safety_net"]["field"], gap["safety_net"]["lab"]
    rows = [
        ("Accuracy", pct(lab["accuracy"]), pct(field["accuracy"]), pct(hint["accuracy"])),
        ("Macro-F1", num(lab["macro_f1"]), num(field["macro_f1"]), num(hint["macro_f1"])),
        ("Calibration error (ECE)", num(cal["lab_ece"]), num(cal["field_ece"]), "—"),
        ("App says 'confident'", pct(safe_l["confident"]["share"]), pct(safe_f["confident"]["share"]), "—"),
        (
            "…and is right when confident",
            pct(safe_l["confident"]["accuracy"]),
            pct(safe_f["confident"]["accuracy"]),
            "—",
        ),
        ("Photos", f"{lab['n']:,}", f"{field['n']:,}", f"{hint['n']:,}"),
    ]
    table = "| Same 28 classes | Lab photos (PlantVillage test) | Real-world photos (PlantDoc) | Real-world + crop hint |\n|---|---|---|---|\n"
    table += "\n".join(f"| {a} | {b} | {c} | {d} |" for a, b, c, d in rows)
    return (
        table + f"\n\nAccuracy drop lab → real-world: **{_ci(gap['accuracy_drop'])} points**. "
        f"PlantDoc photos identical to a PlantVillage photo: {gap['contamination']['plantdoc_photos_identical_to_plantvillage']}.\n\n"
        "_Source: `results/shift/plantdoc_gap.json` (deployed model; PlantDoc = public web photos, not GB photos)._"
    )


def block_leakage_table() -> str:
    leak = _load("results/leakage/leakage_summary.json")
    base = _load("results/baselines/baselines.json")
    if not leak or not base:
        return f"{PENDING}: run `make leakage`."
    rows: dict[str, dict] = {}
    for r in base["rows"]:
        rows.setdefault(r["model"], {})[r["split"]] = r
    lines = [
        "| Model | Naive split acc. | Group-aware acc. | Inflation (points) | Seeds |",
        "|---|---|---|---|---|",
    ]
    for model, splits in sorted(rows.items(), key=lambda kv: -kv[1]["group_aware"]["accuracy_mean"]):
        n, g = splits["naive"], splits["group_aware"]
        lines.append(
            f"| {model} | {pct(n['accuracy_mean'])} ± {n['accuracy_std'] * 100:.1f} | {pct(g['accuracy_mean'])} ± "
            f"{g['accuracy_std'] * 100:.1f} | {(n['accuracy_mean'] - g['accuracy_mean']) * 100:+.1f} | {g['runs']} |"
        )
    return (
        "\n".join(lines)
        + f"\n\nInside the naive test set, photos whose leaf-sibling is in training are classified "
        f"{pct(leak['naive_test_accuracy_exposed'])} correctly vs {pct(leak['naive_test_accuracy_not_exposed'])} for photos "
        f"without one ({pct(leak['naive_exposed_fraction'])} of naive test photos are exposed).\n\n"
        "_Source: `results/leakage/leakage_summary.json`, `results/baselines/baselines.json`._"
    )


def block_fewshot_table() -> str:
    fs = _load("results/shift/fewshot_plantdoc.json")
    if not fs:
        return f"{PENDING}: run `make fewshot`."
    lines = [
        "| k real-world photos per class | Accuracy (mean ± std, 3 seeds) | Macro-F1 | Accuracy with crop hint |",
        "|---|---|---|---|",
    ]
    for i, k in enumerate(fs["k"]):
        lines.append(
            f"| {k} | {pct(fs['accuracy_mean'][i])} ± {fs['accuracy_std'][i] * 100:.1f} | {num(fs['macro_f1_mean'][i])} | "
            f"{pct(fs['crop_hint_accuracy_mean'][i])} ± {fs['crop_hint_accuracy_std'][i] * 100:.1f} |"
        )
    return (
        "\n".join(lines)
        + f"\n\nEvaluated on {fs['n_eval']} held-out PlantDoc test photos ({fs['n_eval_classes']} classes); "
        f"{fs['pool_near_duplicates_removed']} pool photos that nearly duplicated an evaluation photo were removed first. "
        f"Model: {fs['model']}.\n\n_Source: `results/shift/fewshot_plantdoc.json`, figure `results/shift/fewshot_plantdoc.png`._"
    )


def block_ood_table() -> str:
    ood = _load("results/ood/ood_summary.json")
    thr = _load("results/calibration/thresholds.json")
    if not ood:
        return f"{PENDING}: run `make ood`."
    lines = ["| Unfamiliar input | AUROC (max-softmax) | AUROC (energy) | Photos |", "|---|---|---|---|"]
    for s in ood["sets"]:
        lines.append(f"| {s['name']} | {num(s['auroc_msp'])} | {num(s['auroc_energy'])} | {s['n_ood']:,} |")
    text = "\n".join(lines)
    if thr:
        b = thr["behaviour"]
        text += (
            "\n\nWith the thresholds now used by the app (chosen on validation data only): lab photos are answered "
            f"confidently {pct(b['lab_test']['confident']['share'])} of the time; real-world photos "
            f"{pct(b['plantdoc_real_world']['confident']['share'])}"
        )
        if "non_leaf_photos" in b:
            text += f"; non-leaf photos {pct(b['non_leaf_photos']['confident']['share'])}"
        text += '. The rest get "not sure" or "unsupported".'
    return text + "\n\n_Source: `results/ood/ood_summary.json`, `results/calibration/thresholds.json`._"


def block_shortcut() -> str:
    bg = _load("results/background/background_summary.json")
    cam = _load("results/explain/cam_outside_leaf.json")
    if not bg and not cam:
        return f"{PENDING}: run `make background` and `make explain`."
    lines = []
    if bg:
        lines.append(
            f"- A classifier that sees **only the background** (leaf pixels removed) reaches "
            f"{pct(bg['background_only_probe']['accuracy'])} accuracy; one that sees only an 8-pixel border reaches "
            f"{pct(bg['border_only_probe']['accuracy'])} (chance: {pct(bg['chance_accuracy'])}, majority class: "
            f"{pct(bg['majority_class_accuracy'])})."
        )
    if cam:
        lines.append(
            f"- Deployed model, leaf painted grey (background only): {pct(cam['accuracy_leaf_removed'])} accuracy; "
            f"background removed (leaf on black): {pct(cam['accuracy_background_removed'])}; original photos: "
            f"{pct(cam['accuracy_original'])}."
        )
        lines.append(
            f"- Grad-CAM: {pct(cam['cam_mass_outside_leaf_mean'])} of the heat falls outside the leaf, while the background "
            f"covers {pct(cam['background_area_fraction_mean'])} of the image (median ratio "
            f"{num(cam['outside_to_area_ratio_median'], 2)}; below 1 = focused on the leaf)."
        )
    return (
        "\n".join(lines)
        + "\n\n_Source: `results/background/background_summary.json`, `results/explain/cam_outside_leaf.json`._"
    )


def block_sweep_table() -> str:
    path = paths.RESULTS / "sweep" / "summary.md"
    if not path.exists():
        return (
            f"{PENDING}: requires the Colab GPU sweep (`ml/notebooks/colab_run.ipynb`): 3 models × 4 augmentations × "
            "3 seeds on the group-aware split, plus naive-split, imbalance, combined-augmentation and unseen-disease blocks."
        )
    return path.read_text().strip() + "\n\n_Source: `results/sweep/summary.md` (mean ± std over seeds)._"


def block_export() -> str:
    bench = _load("results/export/benchmark.json")
    parity = _load("results/export/parity.json")
    if not bench:
        return f"{PENDING}: run `make export`."
    one, all_ = bench["one_thread"], bench["all_threads"]
    text = (
        f"ONNX model {one['size_mb']} MB; CPU latency per photo {one['latency_ms_median']} ms (1 thread) / "
        f"{all_['latency_ms_median']} ms (all threads), median of {one['runs']} runs on the build machine."
    )
    if parity:
        text += f" ONNX vs PyTorch max |Δlogit| = {parity['max_abs_diff_logits']:.1e} on {parity['n_images']} test photos."
    return text + "\n\n_Source: `results/export/benchmark.json`, `results/export/parity.json`._"


EXTRA_BLOCKS.update(
    {
        "headline_gap": block_headline_gap,
        "leakage_table": block_leakage_table,
        "fewshot_table": block_fewshot_table,
        "ood_table": block_ood_table,
        "shortcut": block_shortcut,
        "sweep_table": block_sweep_table,
        "export": block_export,
    }
)
