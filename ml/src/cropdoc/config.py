"""Plain-YAML configs: base.yaml ← experiment.yaml ← command-line overrides (``key.sub=value``)."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

from cropdoc import paths


def deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge ``override`` into a copy of ``base``."""
    out = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


def parse_override(text: str) -> dict:
    """'train.epochs=3' → {'train': {'epochs': 3}} (values parsed as YAML: numbers, bools, lists)."""
    key, _, raw = text.partition("=")
    value: Any = yaml.safe_load(raw)
    for part in reversed(key.split(".")):
        value = {part: value}
    return value


def load_config(*files: str | Path, overrides: list[str] | None = None) -> dict:
    """Merge base.yaml, the given files (relative to ml/configs or absolute) and overrides."""
    config = yaml.safe_load((paths.CONFIGS / "base.yaml").read_text())
    for file in files:
        path = Path(file)
        path = path if path.is_absolute() or path.exists() else paths.CONFIGS / path
        config = deep_merge(config, yaml.safe_load(path.read_text()) or {})
    for item in overrides or []:
        config = deep_merge(config, parse_override(item))
    return config


def run_id(config: dict) -> str:
    """Stable id from everything that changes the result (not the experiment name, output folders or logging).

    Two experiments with identical settings (e.g. block A's plain-loss ResNet18 and block B's ResNet18 with
    standard augmentation) therefore share one run instead of training twice.
    """
    relevant = {k: v for k, v in config.items() if k not in ("name", "output", "logging")}
    digest = hashlib.sha256(json.dumps(relevant, sort_keys=True, default=str).encode()).hexdigest()[:10]
    return f"s{config.get('seed', 0)}_{digest}"
