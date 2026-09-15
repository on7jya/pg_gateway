"""Dynamic Pydantic model factory from resource field config."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, create_model

from pg_gateway.config.models import PYTHON_TYPES, FieldConfig, FieldType, ResourceConfig


def _annotation(fc: FieldConfig, *, required: bool) -> Any:
    py = PYTHON_TYPES[fc.type]
    if fc.type == FieldType.JSON:
        py = Any
    if required and not fc.nullable:
        return py
    return Optional[py]  # noqa: UP007 — create_model needs Optional


def create_response_model(resource_name: str, config: ResourceConfig) -> type[BaseModel]:
    fields: dict[str, Any] = {}
    for name, fc in config.fields.items():
        if not fc.read:
            continue
        ann = _annotation(fc, required=True)
        fields[name] = (ann, None if fc.nullable or fc.auto or fc.primary_key else ...)
    return create_model(
        f"{_pascal(resource_name)}Response",
        __config__=ConfigDict(from_attributes=True),
        **fields,
    )


def create_create_model(resource_name: str, config: ResourceConfig) -> type[BaseModel]:
    fields: dict[str, Any] = {}
    for name, fc in config.fields.items():
        if fc.primary_key or fc.auto or not fc.write:
            continue
        required = fc.required and not fc.nullable
        ann = _annotation(fc, required=required)
        default = ... if required else None
        fields[name] = (ann, default)
    return create_model(f"{_pascal(resource_name)}Create", **fields)


def create_update_model(resource_name: str, config: ResourceConfig) -> type[BaseModel]:
    """PUT — all writable fields required (except nullable)."""
    fields: dict[str, Any] = {}
    for name, fc in config.fields.items():
        if fc.primary_key or fc.auto or not fc.write:
            continue
        ann = _annotation(fc, required=not fc.nullable)
        default = ... if not fc.nullable else None
        fields[name] = (ann, default)
    return create_model(f"{_pascal(resource_name)}Update", **fields)


def create_patch_model(resource_name: str, config: ResourceConfig) -> type[BaseModel]:
    fields: dict[str, Any] = {}
    for name, fc in config.fields.items():
        if fc.primary_key or fc.auto or not fc.write:
            continue
        ann = _annotation(fc, required=False)
        fields[name] = (ann, None)
    return create_model(f"{_pascal(resource_name)}Patch", **fields)


def create_batch_model(resource_name: str, item_model: type[BaseModel]) -> type[BaseModel]:
    return create_model(
        f"{_pascal(resource_name)}Batch",
        items=(list[item_model], Field(..., min_length=1)),  # type: ignore[valid-type]
    )


def create_upsert_model(resource_name: str, item_model: type[BaseModel]) -> type[BaseModel]:
    return create_model(
        f"{_pascal(resource_name)}Upsert",
        items=(list[item_model], Field(..., min_length=1)),  # type: ignore[valid-type]
    )


def create_bulk_delete_model(resource_name: str) -> type[BaseModel]:
    return create_model(
        f"{_pascal(resource_name)}BulkDelete",
        ids=(Optional[list[Any]], None),
        filters=(Optional[dict[str, dict[str, Any]]], None),
    )


def create_aggregate_request_model(resource_name: str) -> type[BaseModel]:
    return create_model(
        f"{_pascal(resource_name)}AggregateRequest",
        function=(str, ...),
        field=(Optional[str], None),
        group_by=(Optional[list[str]], None),
        filters=(Optional[dict[str, dict[str, Any]]], None),
        include_deleted=(bool, False),
    )


class ListMeta(BaseModel):
    total: int
    limit: int
    offset: int


class ListResponse(BaseModel):
    data: list[Any]
    meta: ListMeta


def _pascal(name: str) -> str:
    return "".join(part.capitalize() for part in name.replace("-", "_").split("_"))


def serialize_row(row: dict[str, Any]) -> dict[str, Any]:
    out = {}
    for k, v in row.items():
        if isinstance(v, UUID):
            out[k] = str(v)
        elif isinstance(v, Decimal):
            out[k] = str(v)
        elif isinstance(v, (datetime, date)):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out
