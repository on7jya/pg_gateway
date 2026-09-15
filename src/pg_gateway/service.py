from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg
from asyncpg.exceptions import UniqueViolationError

from pg_gateway.acl import ACLChecker
from pg_gateway.authz import AuthzPort
from pg_gateway.config.models import AppConfig, ResourceConfig
from pg_gateway.context import RequestContext, get_request_context
from pg_gateway.db import Database
from pg_gateway.errors import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    TimeoutAppError,
    ValidationAppError,
)
from pg_gateway.schemas import serialize_row
from pg_gateway.sql.builder import QueryBuilder, coerce_pk, parse_sort_param


class ResourceService:
    def __init__(self, app_config: AppConfig, db: Database, authz: AuthzPort) -> None:
        self.app_config = app_config
        self.db = db
        self.authz = authz

    def _resource(self, name: str) -> ResourceConfig:
        try:
            return self.app_config.resource(name)
        except KeyError as e:
            raise NotFoundError(f"unknown resource: {name}") from e

    def _acl(self, name: str) -> ACLChecker:
        return ACLChecker(name, self._resource(name))

    def _qb(self, name: str) -> QueryBuilder:
        return QueryBuilder(name, self._resource(name))

    async def _authorize(self, name: str, operation: str) -> RequestContext:
        ctx = get_request_context()
        if not await self.authz.allow(ctx, name, operation):
            raise ForbiddenError("authorization denied", code="AUTHZ_DENIED")
        return ctx

    def _inject_row_context(self, ctx: RequestContext, config: ResourceConfig, payload: dict) -> dict:
        data = dict(payload)
        for rf in config.row_filters:
            ctx_val = getattr(ctx, rf.from_context, None)
            if ctx_val is None and rf.required:
                raise ForbiddenError(
                    f"missing required context '{rf.from_context}'",
                    code="MISSING_TENANT",
                )
            if ctx_val is not None and rf.column in config.fields:
                # Always stamp context onto row for create/upsert
                data[rf.column] = ctx_val
        return data

    async def _run(self, sql: str, args: list[Any], *, many: bool = False, one: bool = False):
        try:
            if one:
                return await self.db.fetchrow(sql, *args)
            if many:
                return await self.db.fetch(sql, *args)
            return await self.db.fetch(sql, *args)
        except UniqueViolationError as e:
            raise ConflictError(str(e), code="UNIQUE_VIOLATION") from e
        except TimeoutError as e:
            raise TimeoutAppError() from e
        except asyncpg.exceptions.QueryCanceledError as e:
            raise TimeoutAppError() from e

    def _present(self, name: str, ctx: RequestContext, row: dict) -> dict:
        acl = self._acl(name)
        return serialize_row(acl.filter_read_payload(ctx, row))

    async def list_resources(
        self,
        name: str,
        *,
        limit: int,
        offset: int,
        sort: str | None = None,
        filters: dict[str, dict[str, Any]] | None = None,
        include: list[str] | None = None,
        include_deleted: bool = False,
    ) -> dict[str, Any]:
        ctx = await self._authorize(name, "list")
        acl = self._acl(name)
        acl.require_operation(ctx, "list")
        config = self._resource(name)
        qb = self._qb(name)
        cols = list(acl.readable_fields(ctx))
        sort_spec = parse_sort_param(sort)
        count_q = qb.build_select(
            ctx,
            filters=filters,
            include_deleted=include_deleted,
            for_count=True,
        )
        total = await self._run(count_q.sql, count_q.args, one=True)
        total_val = int(total["count"]) if total else 0
        q = qb.build_select(
            ctx,
            columns=cols,
            filters=filters,
            sort=sort_spec,
            limit=limit,
            offset=offset,
            include_deleted=include_deleted,
        )
        rows = await self._run(q.sql, q.args, many=True)
        data = [self._present(name, ctx, dict(r)) for r in rows]
        if include:
            data = await self._attach_includes(name, ctx, data, include, include_deleted)
        return {
            "data": data,
            "meta": {"total": total_val, "limit": limit, "offset": offset},
        }

    async def get(
        self,
        name: str,
        id_value: str,
        *,
        include: list[str] | None = None,
        include_deleted: bool = False,
    ) -> dict[str, Any]:
        ctx = await self._authorize(name, "get")
        acl = self._acl(name)
        acl.require_operation(ctx, "get")
        qb = self._qb(name)
        cols = list(acl.readable_fields(ctx))
        q = qb.build_select(
            ctx,
            columns=cols,
            pk_value=coerce_pk(id_value),
            include_deleted=include_deleted,
        )
        row = await self._run(q.sql, q.args, one=True)
        if row is None:
            raise NotFoundError()
        data = self._present(name, ctx, dict(row))
        if include:
            attached = await self._attach_includes(name, ctx, [data], include, include_deleted)
            data = attached[0]
        return data

    async def create(self, name: str, payload: dict[str, Any]) -> dict[str, Any]:
        ctx = await self._authorize(name, "create")
        acl = self._acl(name)
        acl.require_operation(ctx, "create")
        config = self._resource(name)
        data = self._inject_row_context(ctx, config, payload)
        writable = acl.writable_fields(ctx)
        # allow context columns even if not in role write list when stamped
        for rf in config.row_filters:
            if rf.column in data:
                writable = set(writable) | {rf.column}
        filtered = {k: v for k, v in data.items() if k in writable}
        for k in payload:
            fc = config.fields.get(k)
            if fc and (fc.primary_key or fc.auto):
                continue
            if k not in writable and k not in {rf.column for rf in config.row_filters}:
                raise ValidationAppError(f"field not writable: {k}", code="FIELD_DENIED")
        qb = self._qb(name)
        columns = list(filtered.keys())
        q = qb.build_insert(columns, [filtered])
        rows = await self._run(q.sql, q.args, many=True)
        return self._present(name, ctx, dict(rows[0]))

    async def update(self, name: str, id_value: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._mutate(name, id_value, payload, operation="update", partial=False)

    async def patch(self, name: str, id_value: str, payload: dict[str, Any]) -> dict[str, Any]:
        # drop Nones from patch so unset fields stay
        cleaned = {k: v for k, v in payload.items() if v is not None}
        return await self._mutate(name, id_value, cleaned, operation="patch", partial=True)

    async def _mutate(
        self,
        name: str,
        id_value: str,
        payload: dict[str, Any],
        *,
        operation: str,
        partial: bool,
    ) -> dict[str, Any]:
        ctx = await self._authorize(name, operation)
        acl = self._acl(name)
        acl.require_operation(ctx, operation)
        config = self._resource(name)
        writable = acl.writable_fields(ctx)
        for k in payload:
            if k not in writable:
                raise ValidationAppError(f"field not writable: {k}", code="FIELD_DENIED")
        filtered = {k: v for k, v in payload.items() if k in writable}
        if not filtered and not partial:
            raise ValidationAppError("empty update payload", code="EMPTY_PAYLOAD")
        if not filtered:
            return await self.get(name, id_value)
        qb = self._qb(name)
        q = qb.build_update(ctx, coerce_pk(id_value), filtered)
        rows = await self._run(q.sql, q.args, many=True)
        if not rows:
            raise NotFoundError()
        return self._present(name, ctx, dict(rows[0]))

    async def delete(self, name: str, id_value: str) -> dict[str, Any]:
        ctx = await self._authorize(name, "delete")
        acl = self._acl(name)
        acl.require_operation(ctx, "delete")
        config = self._resource(name)
        qb = self._qb(name)
        if config.soft_delete.enabled:
            q = qb.build_soft_delete(ctx, coerce_pk(id_value))
        else:
            q = qb.build_hard_delete(ctx, coerce_pk(id_value))
        rows = await self._run(q.sql, q.args, many=True)
        if not rows:
            raise NotFoundError()
        if config.soft_delete.enabled:
            return self._present(name, ctx, dict(rows[0]))
        return {"id": str(rows[0][config.pk]), "deleted": True}

    async def batch_create(self, name: str, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        ctx = await self._authorize(name, "batch_create")
        acl = self._acl(name)
        acl.require_operation(ctx, "batch_create")
        config = self._resource(name)
        writable = set(acl.writable_fields(ctx))
        for rf in config.row_filters:
            writable.add(rf.column)
        prepared = []
        for item in items:
            data = self._inject_row_context(ctx, config, item)
            for k in item:
                fc = config.fields.get(k)
                if fc and (fc.primary_key or fc.auto):
                    continue
                if k not in writable and k not in {rf.column for rf in config.row_filters}:
                    raise ValidationAppError(f"field not writable: {k}", code="FIELD_DENIED")
            prepared.append({k: v for k, v in data.items() if k in writable})
        if not prepared:
            raise ValidationAppError("empty batch", code="EMPTY_PAYLOAD")
        columns = list(prepared[0].keys())
        for row in prepared:
            if set(row.keys()) != set(columns):
                # union columns
                columns = list(dict.fromkeys([*columns, *row.keys()]))
        qb = self._qb(name)
        q = qb.build_insert(columns, prepared)
        rows = await self._run(q.sql, q.args, many=True)
        return [self._present(name, ctx, dict(r)) for r in rows]

    async def upsert(self, name: str, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        ctx = await self._authorize(name, "upsert")
        acl = self._acl(name)
        acl.require_operation(ctx, "upsert")
        config = self._resource(name)
        if not config.upsert_keys:
            raise ValidationAppError("upsert_keys not configured", code="NO_UPSERT_KEYS")
        writable = set(acl.writable_fields(ctx))
        for rf in config.row_filters:
            writable.add(rf.column)
        for key in config.upsert_keys:
            writable.add(key)
        prepared = []
        for item in items:
            data = self._inject_row_context(ctx, config, item)
            prepared.append({k: v for k, v in data.items() if k in writable})
        columns = list(dict.fromkeys(k for row in prepared for k in row))
        update_cols = [c for c in columns if c not in config.upsert_keys and c != config.pk]
        qb = self._qb(name)
        q = qb.build_upsert(columns, prepared, config.upsert_keys, update_cols)
        rows = await self._run(q.sql, q.args, many=True)
        return [self._present(name, ctx, dict(r)) for r in rows]

    async def bulk_delete(
        self,
        name: str,
        *,
        ids: list[Any] | None = None,
        filters: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        ctx = await self._authorize(name, "bulk_delete")
        acl = self._acl(name)
        acl.require_operation(ctx, "bulk_delete")
        config = self._resource(name)
        coerced_ids = [coerce_pk(str(i)) if not isinstance(i, (int, UUID)) else i for i in (ids or [])]
        qb = self._qb(name)
        soft = config.soft_delete.enabled
        q = qb.build_bulk_delete(ctx, ids=coerced_ids or None, filters=filters, soft=soft)
        rows = await self._run(q.sql, q.args, many=True)
        return {"deleted": len(rows), "ids": [str(r[config.pk]) for r in rows]}

    async def aggregate(
        self,
        name: str,
        *,
        function: str,
        field: str | None = None,
        group_by: list[str] | None = None,
        filters: dict[str, dict[str, Any]] | None = None,
        include_deleted: bool = False,
    ) -> dict[str, Any]:
        ctx = await self._authorize(name, "aggregate")
        acl = self._acl(name)
        acl.require_operation(ctx, "aggregate")
        qb = self._qb(name)
        q = qb.build_aggregate(
            ctx,
            function=function,
            field=field,
            group_by=group_by,
            filters=filters,
            include_deleted=include_deleted,
        )
        rows = await self._run(q.sql, q.args, many=True)
        results = [serialize_row(dict(r)) for r in rows]
        return {"data": results}

    async def _attach_includes(
        self,
        name: str,
        ctx: RequestContext,
        data: list[dict[str, Any]],
        include: list[str],
        include_deleted: bool,
    ) -> list[dict[str, Any]]:
        config = self._resource(name)
        for rel_name in include:
            if "." in rel_name or rel_name not in config.relations:
                raise ValidationAppError(f"unknown relation: {rel_name}", code="BAD_INCLUDE")
            rel = config.relations[rel_name]
            related = self._resource(rel.resource)
            local_vals = [row.get(rel.local) for row in data if row.get(rel.local) is not None]
            # coerce string UUIDs back if needed
            q = QueryBuilder(rel.resource, related).build_related_select(
                related,
                foreign_col=rel.foreign,
                local_values=local_vals,
                ctx=ctx,
                include_deleted=include_deleted,
            )
            related_acl = ACLChecker(rel.resource, related)
            if not await self.authz.allow(ctx, rel.resource, "list"):
                raise ForbiddenError("authorization denied", code="AUTHZ_DENIED")
            related_acl.require_operation(ctx, "list")
            rows = await self._run(q.sql, q.args, many=True)
            related_rows = [
                serialize_row(related_acl.filter_read_payload(ctx, dict(r))) for r in rows
            ]
            # index by foreign key
            from collections import defaultdict

            by_fk: dict[Any, list[dict]] = defaultdict(list)
            for rr in related_rows:
                by_fk[rr.get(rel.foreign)].append(rr)
            # also try string keys
            by_fk_str = {str(k): v for k, v in by_fk.items()}

            for row in data:
                key = row.get(rel.local)
                matches = by_fk.get(key) or by_fk_str.get(str(key), [])
                if rel.type.value in ("one_to_many",):
                    row[rel_name] = matches
                else:
                    row[rel_name] = matches[0] if matches else None
        return data


def parse_filter_query_params(query_params: Any) -> dict[str, dict[str, Any]]:
    """Parse filter[field][op]=value from query params."""
    filters: dict[str, dict[str, Any]] = {}
    for key, value in query_params.multi_items():
        if not key.startswith("filter[") or "]" not in key:
            continue
        # filter[field][op]
        inner = key[len("filter[") :]
        if "],[" in inner or "][" in inner:
            # filter[status][eq]
            parts = inner.rstrip("]").split("][")
            if len(parts) != 2:
                raise ValidationAppError(f"bad filter key: {key}", code="BAD_FILTER")
            field, op = parts[0], parts[1]
        else:
            raise ValidationAppError(f"bad filter key: {key}", code="BAD_FILTER")
        filters.setdefault(field, {})[op] = value
    return filters
