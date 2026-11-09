"""Safety checks on the disease library content (backend/app/data/diseases.json)."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DISEASES = json.loads((ROOT / "backend" / "app" / "data" / "diseases.json").read_text(encoding="utf-8"))
ENTRIES = DISEASES["diseases"]
FALLBACK = DISEASES["meta"]["extension_fallback"]

# Product names and dose/interval patterns that must never appear (cultural practices only).
BANNED_WORDS = [
    "mancozeb",
    "chlorothalonil",
    "captan",
    "copper",
    "sulfur",
    "sulphur",
    "streptomycin",
    "oxytetracycline",
    "imidacloprid",
    "abamectin",
    "neem",
    "fungicide",
    "insecticide",
    "bactericide",
    "pesticide",
    "spray",
    "metalaxyl",
    "azoxystrobin",
    "propiconazole",
    "myclobutanil",
    "kasugamycin",
    "bifenthrin",
]
BANNED_PATTERNS = [
    r"\b\d+(\.\d+)?\s*(ml|g|kg|l|oz|lb)\s*/",
    r"\bevery\s+\d+\s*(-\s*\d+\s*)?days?\b",
    r"\bdos(e|age)\b",
]


def _texts(entry: dict) -> list[str]:
    return [
        entry["description"],
        entry["spread"],
        entry["most_affected_part"],
        *entry["symptoms"],
        *entry["general_management"],
    ]


def test_one_entry_per_model_class():
    classes_file = ROOT / "models" / "active" / "classes.json"
    if not classes_file.exists():
        pytest.skip("no model installed")
    class_ids = {c["id"] for c in json.loads(classes_file.read_text())["classes"]}
    assert {e["id"] for e in ENTRIES} == class_ids


@pytest.mark.parametrize("entry", ENTRIES, ids=lambda e: e["id"])
def test_entry_is_complete_and_sourced(entry):
    for field in ("crop", "disease", "category", "description", "spread", "most_affected_part"):
        assert entry[field].strip(), field
    assert entry["symptoms"] and entry["general_management"]
    assert entry["sources"] and all(url.startswith("https://") for url in entry["sources"])
    assert isinstance(entry["needs_review"], bool)


@pytest.mark.parametrize("entry", ENTRIES, ids=lambda e: e["id"])
def test_no_chemicals_doses_or_spray_intervals(entry):
    text = " ".join(_texts(entry)).lower()
    found = [w for w in BANNED_WORDS if re.search(rf"\b{w}", text)]
    found += [p for p in BANNED_PATTERNS if re.search(p, text)]
    assert not found, f"{entry['id']}: {found}"


def test_fallback_line_is_the_required_wording():
    assert FALLBACK == "Consult your local agriculture extension officer for approved products and doses."
