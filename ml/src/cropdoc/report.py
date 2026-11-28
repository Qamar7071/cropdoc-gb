"""Fill the number blocks in README.md and MODEL_CARD.md from result files (``make report``).

Docs contain marker pairs like ``<!-- BEGIN:quick_metrics -->`` … ``<!-- END:quick_metrics -->``.
Everything between them is regenerated from ``results/`` and ``models/active/``; nothing numeric is
typed by hand. A missing result file renders as **PENDING**. ``--check`` exits 1 if a block is stale
(used by CI so the docs can never drift from the results).
"""

from __future__ import annotations

import argparse
import contextlib
import importlib
import json
import re
import sys
from collections.abc import Callable

from cropdoc import paths

PENDING = "**PENDING**"


def _load(relative: str) -> dict | None:
    path = paths.ROOT / relative
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def pct(value: float | None, digits: int = 1) -> str:
    return "—" if value is None else f"{value * 100:.{digits}f}%"


def num(value: float | None, digits: int = 3) -> str:
    return "—" if value is None else f"{value:.{digits}f}"


# ----------------------------------------------------------------------------- blocks
def block_quick_metrics() -> str:
    card = _load("models/active/model_card.json")
    metrics = _load("results/quick_model/metrics.json")
    if not card or not metrics:
        return f"{PENDING}: run `make train` (scripts/train_quick.py)."
    test, val, th = metrics["test"], metrics["val"], metrics["thresholds"]
    rows = [
        ("Test accuracy (group-aware split, lab photos)", pct(test["accuracy"], 2)),
        ("Test macro-F1", num(test["macro_f1"])),
        ("Test photos", f"{test['n']:,}"),
        ("Validation accuracy / macro-F1", f"{pct(val['accuracy'], 2)} / {num(val['macro_f1'])}"),
        (
            "Calibration error (ECE) before → after temperature",
            f"{num(test['ece_uncalibrated'], 4)} → {num(test['ece_calibrated'], 4)}",
        ),
        ("Temperature (fitted on validation)", num(metrics["temperature"])),
        (
            "'Confident' threshold / test coverage / accuracy when confident",
            f"{num(th['min_confidence'], 2)} / {pct(th['test_coverage_confident'])} / {pct(th['test_accuracy_confident'])}",
        ),
        ("Training time (CPU only)", f"{metrics['timing_minutes']['total']:.1f} min"),
        ("Model", f"{card['architecture']} · `{card['model_version']}`"),
    ]
    table = "| Metric | Value |\n|---|---|\n" + "\n".join(f"| {k} | {v} |" for k, v in rows)
    return table + "\n\n_Source: `results/quick_model/metrics.json`, `models/active/model_card.json`._"


def block_data_facts() -> str:
    groups = _load("results/data_audit/group_stats.json")
    exposure = _load("results/data_audit/naive_split_exposure.json")
    split = _load("ml/splits/manifest.json")
    counts = _load("results/data_audit/class_counts.json")
    if not (groups and exposure and split):
        return f"{PENDING}: run `make split`."
    sizes = split["splits"]["group_aware"]["per_split"]
    lines = [
        f"- {groups['n_images']:,} PlantVillage photos in 38 classes"
        + (f" ({counts['min']}–{counts['max']} per class)." if counts else "."),
        f"- {groups['images_in_multi_photo_groups']:,} photos belong to groups of the same physical leaf "
        f"(official leaf map + near-duplicate detection); {groups['n_groups']:,} groups in total.",
        f"- A naive random split puts a same-leaf sibling of **{pct(exposure['exposed_fraction'])}** of test photos "
        f"into training ({exposure['exposed_test_images']:,} of {exposure['test_images']:,}).",
        f"- Group-aware split used for every reported number: {sizes['train']:,} train / {sizes['val']:,} val / "
        f"{sizes['test']:,} test, {split['groups_crossing_splits']['group_aware']} groups crossing splits "
        f"(SHA256 `{split['splits']['group_aware']['sha256_csv'][:12]}…`).",
    ]
    return "\n".join(lines) + "\n\n_Source: `results/data_audit/`, `ml/splits/manifest.json`._"


def block_field_model() -> str:
    """Model v1 (lab photos only) vs v2 (lab + real-world photos) on the same unseen test photos."""
    summary = _load("results/field_model/summary.json")
    if not summary:
        return f"{PENDING}: run `make train-field` (CPU, about 1 hour)."
    v1, v2 = summary["v1"], summary["v2"]
    rows = [
        ("Lab test photos: accuracy", "lab_test", "accuracy", lambda v: pct(v)),
        ("Lab test photos: macro-F1", "lab_test", "macro_f1", num),
        ("Real-world test photos: accuracy", "field_test", "accuracy", lambda v: pct(v)),
        ("Real-world test photos: macro-F1", "field_test", "macro_f1", num),
        ("Real-world: calibration error (ECE)", "field_test", "ece_calibrated", num),
        ("Real-world: share answered 'confident'", "field_test", "confident_share", lambda v: pct(v)),
        ("Real-world: accuracy when 'confident'", "field_test", "confident_accuracy", lambda v: pct(v)),
    ]
    lines = ["| Measure | v1 (deployed, lab photos only) | v2 (lab + real-world photos) |", "|---|---|---|"]
    for label, domain, key, fmt in rows:
        lines.append(f"| {label} | {fmt(v1[domain][key])} | {fmt(v2[domain][key])} |")
    lines.append(
        f"| Non-leaf photos answered 'confident' | {pct(v1['non_leaf_confident_share'])} "
        f"| {pct(v2['non_leaf_confident_share'])} |"
    )
    n_lab, n_field = v1["lab_test"]["n"], v1["field_test"]["n"]
    diff = summary["field_accuracy_difference_v2_minus_v1"]
    lab_diff = summary["lab_accuracy_difference_v2_minus_v1"]
    checks = summary["promotion_checks"]
    names = {
        "field_macro_f1_gain": "real-world macro-F1 gain",
        "lab_macro_f1_drop": "lab macro-F1 drop",
        "non_leaf_confident_share": "non-leaf photos answered 'confident'",
    }

    def show(key: str, value: float) -> str:
        return pct(value) if key == "non_leaf_confident_share" else f"{value * 100:.2f} points"

    verdicts = []
    for key, check in checks.items():
        sign, limit = check["required"].split()  # e.g. ">= 0.05"
        need = f"{'≥' if sign == '>=' else '≤'} {show(key, float(limit))}"
        verdicts.append(
            f"{names.get(key, key)} {show(key, check['value'])} (rule: {need}) {'✓' if check['ok'] else '✗'}"
        )
    decision = (
        "**v2 passed every rule and is the deployed model.**"
        if summary["promoted"]
        else "**v2 is not deployed**: it failed a rule fixed before testing, so the app keeps v1."
    )
    return (
        "\n".join(lines)
        + f"\n\nTest photos: {n_lab:,} lab, {n_field:,} real-world (PlantDoc web photos, not Gilgit-Baltistan). "
        f"Real-world accuracy difference v2 − v1: {diff['difference'] * 100:+.1f} points "
        f"(95% CI {diff['ci95'][0] * 100:+.1f} to {diff['ci95'][1] * 100:+.1f}); lab: "
        f"{lab_diff['difference'] * 100:+.1f} points (95% CI {lab_diff['ci95'][0] * 100:+.1f} to "
        f"{lab_diff['ci95'][1] * 100:+.1f}). Rules: "
        + "; ".join(verdicts)
        + f". {decision}\n\n_Source: `results/field_model/summary.json` (from `comparison.json`)._"
    )


RESEARCH_FILES = [
    ("Leakage: naive vs group-aware split", "results/leakage/leakage_summary.json"),
    ("Background uniformity / background-only probe", "results/background/background_summary.json"),
    ("Lab → real-world photos (PlantDoc)", "results/shift/plantdoc_gap.json"),
    ("Model v2 trained with real-world photos (v1 vs v2)", "results/field_model/summary.json"),
    ("Lab → Gilgit-Baltistan field photos", "results/shift/field_gap.json"),
    ("Calibration (ECE, reliability)", "results/calibration/calibration_summary.json"),
    ("OOD detection (AUROC)", "results/ood/ood_summary.json"),
    ("Few-shot adaptation (PlantDoc)", "results/shift/fewshot_plantdoc.json"),
    ("Few-shot adaptation (GB photos)", "results/shift/fewshot_field.json"),
    ("Grad-CAM mass outside the leaf", "results/explain/cam_outside_leaf.json"),
    ("Model × augmentation sweep (3 seeds, Colab)", "results/sweep/summary.json"),
]


def block_research_status() -> str:
    rows = []
    for title, rel in RESEARCH_FILES:
        rows.append(f"| {title} | {'ready' if (paths.ROOT / rel).exists() else PENDING} | `{rel}` |")
    return "| Study | Status | Result file |\n|---|---|---|\n" + "\n".join(rows)


BLOCKS: dict[str, Callable[[], str]] = {
    "quick_metrics": block_quick_metrics,
    "data_facts": block_data_facts,
    "research_status": block_research_status,
    "field_model": block_field_model,
}
EXTRA_BLOCKS: dict[str, Callable[[], str]] = {}  # research blocks register here (cropdoc.report_research)


def render(text: str) -> str:
    """Replace every known marker block in ``text``."""
    blocks = {**BLOCKS, **EXTRA_BLOCKS}

    def replace(match: re.Match) -> str:
        name = match.group(1)
        if name not in blocks:
            return match.group(0)
        return f"<!-- BEGIN:{name} -->\n{blocks[name]().strip()}\n<!-- END:{name} -->"

    return re.sub(r"<!-- BEGIN:(\w+) -->.*?<!-- END:\1 -->", replace, text, flags=re.DOTALL)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--check", action="store_true", help="exit 1 if a doc is out of date")
    args = parser.parse_args(argv)
    with contextlib.suppress(ImportError):  # optional research blocks (Milestone 2)
        importlib.import_module("cropdoc.report_research")
        # under `python -m`, this file runs as __main__ and the research module registered its blocks on the
        # importable copy (cropdoc.report): merge them here
        EXTRA_BLOCKS.update(importlib.import_module("cropdoc.report").EXTRA_BLOCKS)
    stale = []
    for doc in ("README.md", "MODEL_CARD.md"):
        path = paths.ROOT / doc
        if not path.exists():
            continue
        old = path.read_text(encoding="utf-8")
        new = render(old)
        if new != old:
            stale.append(doc)
            if not args.check:
                path.write_text(new, encoding="utf-8")
    if args.check and stale:
        print(f"out of date: {', '.join(stale)} (run `make report`)")
        return 1
    print("docs up to date" if not stale else f"updated: {', '.join(stale)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
