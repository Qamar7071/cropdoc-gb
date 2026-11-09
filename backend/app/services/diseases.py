"""Disease library: loads ``app/data/diseases.json`` (one entry per model class).

Content rules (safety): cultural practices only, no chemical names or doses, sources listed,
and ``needs_review`` stays true until a person has checked the text against the sources.
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

    @classmethod
    def load(cls, path: Path) -> DiseaseLibrary:
        """Load the JSON file; a missing file gives an empty library (the API still works)."""
        if not path.exists():
            return cls()
        payload = json.loads(path.read_text(encoding="utf-8"))
        entries = {item["id"]: item for item in payload.get("diseases", [])}
        return cls(entries=entries, meta=payload.get("meta", {}))

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
