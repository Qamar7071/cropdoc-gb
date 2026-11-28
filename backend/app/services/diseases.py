"""Disease library: ``app/data/diseases.json`` (English, one entry per model class) plus the Urdu layer
``app/data/diseases_ur.json`` (same keys), served together as a bilingual report.

Content rules (safety): cultural practices and generic treatment categories only (never product or
active-ingredient names, doses or spray schedules), sources listed, and ``needs_review`` stays true
until a person has checked the text. The Urdu text is AI-drafted and flagged for native review.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

EXTENSION_FALLBACK = "Consult your local agriculture extension officer for approved products and doses."


def slug(class_id: str) -> str:
    """URL/folder-safe class id (must match ml/src/cropdoc/data/classes.py::slug)."""
    return re.sub(r"[^A-Za-z0-9]+", "_", class_id).strip("_")


@dataclass
class DiseaseLibrary:
    """In-memory view of the disease library keyed by class id (e.g. ``Potato___Early_blight``)."""

    entries: dict[str, dict[str, Any]] = field(default_factory=dict)
    meta: dict[str, Any] = field(default_factory=dict)
    urdu: dict[str, dict[str, Any]] = field(default_factory=dict)
    urdu_meta: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> DiseaseLibrary:
        """Load the JSON files; missing files give an empty library / no Urdu (the API still works)."""
        if not path.exists():
            return cls()
        payload = json.loads(path.read_text(encoding="utf-8"))
        entries = {item["id"]: item for item in payload.get("diseases", [])}
        urdu_path = path.with_name("diseases_ur.json")
        urdu_payload = json.loads(urdu_path.read_text(encoding="utf-8")) if urdu_path.exists() else {}
        return cls(
            entries=entries,
            meta=payload.get("meta", {}),
            urdu=urdu_payload.get("diseases", {}),
            urdu_meta=urdu_payload.get("meta", {}),
        )

    def crop_ur(self, crop: str) -> str:
        return self.urdu_meta.get("crops", {}).get(crop, "")

    def report(self, class_id: str) -> dict[str, Any]:
        """Everything the result screen shows, in English and Urdu side by side.

        Symptoms are split into early (the first listed sign) and advanced (the rest). The risk level is
        the disease's general potential for loss from the cited sources, never measured from the photo.
        """
        entry = self.get(class_id) or {}
        ur = self.urdu.get(class_id, {})

        def pair(en_key: str, ur_key: str | None = None) -> dict[str, Any]:
            return {"en": entry.get(en_key, ""), "ur": ur.get(ur_key or en_key, "")}

        def pair_list(
            en_key: str, ur_key: str | None = None, sl: slice = slice(None)
        ) -> dict[str, list[str]]:
            return {"en": list(entry.get(en_key, []))[sl], "ur": list(ur.get(ur_key or en_key, []))[sl]}

        return {
            "id": class_id,
            "crop": {"en": entry.get("crop", ""), "ur": self.crop_ur(entry.get("crop", ""))},
            "name": {"en": entry.get("disease", ""), "ur": ur.get("name", "")},
            "category": entry.get("category", ""),
            "healthy": entry.get("category") == "healthy",
            "pathogen": entry.get("pathogen", ""),
            "description": pair("description"),
            "risk_level": entry.get("risk_level", ""),
            "risk_reason": pair("risk_reason"),
            "symptoms_early": pair_list("symptoms", sl=slice(0, 1)),
            "symptoms_advanced": pair_list("symptoms", sl=slice(1, None)),
            "spread": pair("spread"),
            "causes": pair_list("causes"),
            "immediate_actions": pair_list("immediate_actions"),
            "prevention": pair_list("general_management", "prevention"),
            "treatment_categories": pair_list("treatment_categories"),
            "call_expert_when": pair_list("call_expert_when"),
            "extension_fallback": {
                "en": EXTENSION_FALLBACK,
                "ur": self.urdu_meta.get("extension_fallback", ""),
            },
            "sources": list(entry.get("sources", [])),
            "needs_review": bool(entry.get("needs_review", True)),
            "urdu_needs_review": bool(self.urdu_meta.get("needs_native_review", True)),
        }

    def get(self, class_id: str) -> dict[str, Any] | None:
        """Full entry for one class, or None."""
        return self.entries.get(class_id)

    def list(self, crop: str | None = None, q: str | None = None) -> list[dict[str, Any]]:
        """Entries filtered by crop and a case-insensitive text search."""
        items = list(self.entries.values())
        if crop:
            items = [e for e in items if e.get("crop", "").lower() == crop.lower()]
        if q:
            needle = q.lower()
            items = [
                e
                for e in items
                if needle
                in " ".join([e.get("crop", ""), e.get("disease", ""), e.get("description", "")]).lower()
            ]
        return sorted(items, key=lambda e: (e.get("crop", ""), e.get("disease", "")))

    def recommendations(self, class_id: str, limit: int = 3) -> list[str]:
        """Short checklist for the result card: cultural practices plus the extension-officer line."""
        entry = self.get(class_id) or {}
        tips = list(entry.get("general_management", []))[: max(limit - 1, 0)]
        if entry.get("category") != "healthy":
            tips.append(EXTENSION_FALLBACK)
        return tips[:limit]
