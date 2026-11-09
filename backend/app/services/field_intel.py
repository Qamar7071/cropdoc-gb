"""Read research results for the Field Intelligence page.

Each section is backed by one JSON file in ``results/``. A missing file is reported as
``pending`` with the reason, so the page can show an honest PENDING state instead of numbers.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SECTIONS: dict[str, dict[str, str]] = {
    "leakage": {
        "file": "leakage/leakage_summary.json",
        "title": "Leakage: naive vs group-aware split",
        "pending": "Run `make split` and `make leakage` (CPU) to measure how much a naive split inflates accuracy.",
    },
    "background": {
        "file": "background/background_summary.json",
        "title": "Background uniformity (shortcut risk)",
        "pending": "Run `make background` (CPU).",
    },
    "plantdoc_gap": {
        "file": "shift/plantdoc_gap.json",
        "title": "Lab vs real-world photos (PlantDoc, public web photos)",
        "pending": "Run `make shift` (CPU) after `make data` downloads PlantDoc.",
    },
    "field_gap": {
        "file": "shift/field_gap.json",
        "title": "Lab vs Gilgit-Baltistan field photos",
        "pending": "PENDING: needs field photos in data/field_test/<class>/ (see docs/field_collection_guide.md).",
    },
    "calibration": {
        "file": "calibration/calibration_summary.json",
        "title": "Calibration (is 90% confidence right 90% of the time?)",
        "pending": "Run `make calibrate`.",
    },
    "ood": {
        "file": "ood/ood_summary.json",
        "title": "Detecting unsupported inputs",
        "pending": "Run `make ood`.",
    },
    "fewshot_plantdoc": {
        "file": "shift/fewshot_plantdoc.json",
        "title": "Few-shot adaptation with k real-world photos per class (PlantDoc)",
        "pending": "Run `make fewshot`.",
    },
    "fewshot_field": {
        "file": "shift/fewshot_field.json",
        "title": "Few-shot adaptation with k GB field photos per class",
        "pending": "PENDING: needs field photos in data/field_test/<class>/.",
    },
    "cam_focus": {
        "file": "explain/cam_outside_leaf.json",
        "title": "Does the model look at the leaf? (Grad-CAM outside the leaf mask)",
        "pending": "Run `make explain`.",
    },
    "sweep": {
        "file": "sweep/summary.json",
        "title": "Model × augmentation experiment matrix (3 seeds each)",
        "pending": "PENDING: requires the Colab sweep (ml/notebooks/colab_run.ipynb).",
    },
}


def load_sections(results_dir: Path) -> dict[str, Any]:
    """Return every section as ``{status, title, source, data | pending_reason}``."""
    sections: dict[str, Any] = {}
    for key, spec in SECTIONS.items():
        path = results_dir / spec["file"]
        entry: dict[str, Any] = {"title": spec["title"], "source": f"results/{spec['file']}"}
        if path.exists():
            try:
                entry.update(status="ready", data=json.loads(path.read_text(encoding="utf-8")))
            except json.JSONDecodeError:
                entry.update(status="pending", pending_reason=f"{entry['source']} is not valid JSON.")
        else:
            entry.update(status="pending", pending_reason=spec["pending"])
        sections[key] = entry
    return sections
