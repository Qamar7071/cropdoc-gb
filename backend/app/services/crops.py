"""Crop information and farming tips (``app/data/crops.json``, ``app/data/tips.json``), English + Urdu.

The scanner covers only the 38 model classes; crop pages also cover important Pakistani crops the
scanner does not know yet (wheat, rice, cotton, sugarcane, mango), clearly labelled as such.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class CropLibrary:
    crops: list[dict[str, Any]] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)
    tips: list[dict[str, Any]] = field(default_factory=list)
    tips_meta: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(cls, crops_path: Path, tips_path: Path) -> CropLibrary:
        crops = json.loads(crops_path.read_text(encoding="utf-8")) if crops_path.exists() else {}
        tips = json.loads(tips_path.read_text(encoding="utf-8")) if tips_path.exists() else {}
        return cls(
            crops=crops.get("crops", []),
            meta=crops.get("meta", {}),
            tips=tips.get("tips", []),
            tips_meta=tips.get("meta", {}),
        )

    def get(self, crop_id: str) -> dict[str, Any] | None:
        return next((c for c in self.crops if c["id"] == crop_id), None)
