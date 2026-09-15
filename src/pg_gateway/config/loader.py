from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from pg_gateway.config.models import AppConfig


def load_yaml(path: str | Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"config root must be a mapping: {path}")
    return data


def load_config(path: str | Path) -> AppConfig:
    """Load and validate gateway YAML config (startup only)."""
    raw = load_yaml(path)
    return AppConfig.model_validate(raw)
