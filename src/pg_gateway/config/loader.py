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


def merge_accounts_overlay(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Merge accounts overlay into base config (accounts + optional authz/resources)."""
    merged = dict(base)

    if "accounts" in overlay:
        merged["accounts"] = overlay["accounts"]

    if "authz" in overlay:
        authz = dict(merged.get("authz") or {})
        authz.update(overlay["authz"])
        merged["authz"] = authz

    if "resources" in overlay:
        resources = {name: dict(cfg) for name, cfg in (merged.get("resources") or {}).items()}
        for name, overrides in overlay["resources"].items():
            if name not in resources:
                raise ValueError(f"accounts overlay references unknown resource: {name!r}")
            if not isinstance(overrides, dict):
                raise ValueError(f"accounts overlay resources.{name} must be a mapping")
            resources[name] = {**resources[name], **overrides}
        merged["resources"] = resources

    return merged


def load_config(
    path: str | Path,
    *,
    accounts_path: str | Path | None = None,
) -> AppConfig:
    """Load and validate gateway YAML config (startup only).

    Optional ``accounts_path`` overlays ``accounts`` and optionally ``authz`` /
    per-resource keys (e.g. ``row_filters``) for cert_dn / ТУЗ deployments.
    """
    raw = load_yaml(path)
    if accounts_path:
        overlay = load_yaml(accounts_path)
        raw = merge_accounts_overlay(raw, overlay)
    return AppConfig.model_validate(raw)
