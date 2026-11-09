"""Central file locations, so every script agrees on where things live.

All paths are relative to the repository root, which is found by walking up from this file.
Override the data folder with the CROPDOC_DATA environment variable (handy on Colab, where
data lives on the fast local disk while results are copied to Google Drive).
"""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DATA = Path(os.environ.get("CROPDOC_DATA", ROOT / "data"))
RAW = DATA / "raw"
PLANTVILLAGE = RAW / "PlantVillage-Dataset"
PV_COLOR = PLANTVILLAGE / "raw" / "color"
PV_SEGMENTED = PLANTVILLAGE / "raw" / "segmented"
PV_LEAF_MAP = PLANTVILLAGE / "leaf-map.json"
PLANTDOC = RAW / "PlantDoc-Dataset"
FIELD_TEST = DATA / "field_test"
CACHE = Path(os.environ.get("CROPDOC_CACHE", ROOT / "ml" / "cache"))
RUNS = Path(os.environ.get("CROPDOC_RUNS", ROOT / "ml" / "runs"))
SPLITS = ROOT / "ml" / "splits"
CONFIGS = ROOT / "ml" / "configs"
RESULTS = ROOT / "results"
MODELS_ACTIVE = ROOT / "models" / "active"
WEIGHTS = CACHE / "weights"
