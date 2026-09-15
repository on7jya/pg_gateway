"""Safe SQL query builder — identifiers only from config whitelist."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from pg_gateway.config.models import ResourceConfig
from pg_gateway.context import RequestContext
from pg_gateway.errors import ForbiddenError, ValidationAppError

# Identifiers: letters, digits, underscore only
_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

FILTER_OPS = frozenset(
    {"eq", "ne", "gt", "gte", "lt", "lte", "in", "like", "ilike", "is_null"}
)

OP_SQL = {
    "eq": "=",
    "ne": "<>",
    "gt": ">",
    "gte": ">=",
    "lt": "<",
    "lte": "<=",
    "like": "LIKE",
    "ilike": "ILIKE",
}


def quote_ident(name: str, *, allowed: set[str] | None = None) -> str:
    if not _IDENT_RE.match(name):
        raise ValidationAppError(f"invalid identifier: {name}", code="INVALID_IDENTIFIER")
    if allowed is not None and name not in allowed:
        raise ValidationAppError(f"identifier not allowed: {name}", code="IDENTIFIER_DENIED")
    return f'"{name}"'


@dataclass
class BoundQuery:
    sql: str
    args: list[Any] = field(default_factory=list)


class QueryBuilder:
    def __init__(self, resource_name: str, config: ResourceConfig) -> None:
        self.resource_name = resource_name
        self.config = config
        self.allowed = set(config.fields.keys()) | {config.table, config.pk}
        for rf in config.row_filters:
            self.allowed.add(rf.column)
        if config.soft_delete.enabled:
            self.allowed.add(config.soft_delete.field)
        self.table = quote_ident(config.table, allowed=self.allowed)

    def _col(self, name: str) -> str:
        return quote_ident(name, allowed=self.allowed)

    def _next_arg(self, args: list[Any], value: Any) -> str:
        args.append(value)
        return f"${len(args)}"

    def apply_row_filters(
        self,
        ctx: RequestContext,
        args: list[Any],
        clauses: list[str],
    ) -> None:
        for rf in self.config.row_filters:
            ctx_val = getattr(ctx, rf.from_context, None)
            if ctx_val is None:
                if rf.required:
                    raise ForbiddenError(
                        f"missing required context '{rf.from_context}'",
                        code="MISSING_TENANT",
                    )
                continue
            ph = self._next_arg(args, ctx_val)
            clauses.append(f"{self._col(rf.column)} = {ph}")

    def apply_soft_delete(
        self,
        clauses: list[str],
        *,
        include_deleted: bool = False,
    ) -> None:
        if self.config.soft_delete.enabled and not include_deleted:
            clauses.append(f"{self._col(self.config.soft_delete.field)} IS NULL")

    def parse_filters(
        self,
        raw: dict[str, dict[str, Any]],
        args: list[Any],
        clauses: list[str],
        *,
        filterable: list[str] | None = None,
    ) -> None:
        allowed_fields = set(filterable or self.config.filterable)
        for field_name, ops in raw.items():
            if field_name not in allowed_fields:
                raise ValidationAppError(
                    f"field not filterable: {field_name}",
                    code="FILTER_DENIED",
                )
            if field_name not in self.config.fields:
                raise ValidationAppError(
                    f"unknown filter field: {field_name}",
                    code="UNKNOWN_FIELD",
                )
            for op, value in ops.items():
                if op not in FILTER_OPS:
                    raise ValidationAppError(f"unsupported filter op: {op}", code="BAD_FILTER_OP")
                col = self._col(field_name)
                if op == "is_null":
                    truthy = str(value).lower() in {"1", "true", "yes"}
                    clauses.append(f"{col} IS NULL" if truthy else f"{col} IS NOT NULL")
                elif op == "in":
                    if isinstance(value, str):
                        items = [v.strip() for v in value.split(",") if v.strip()]
                    elif isinstance(value, list):
                        items = value
                    else:
                        raise ValidationAppError("in filter expects list or csv", code="BAD_FILTER")
                    if not items:
                        raise ValidationAppError("in filter empty", code="BAD_FILTER")
                    placeholders = [self._next_arg(args, item) for item in items]
                    clauses.append(f"{col} IN ({', '.join(placeholders)})")
                else:
                    ph = self._next_arg(args, value)
                    clauses.append(f"{col} {OP_SQL[op]} {ph}")

    def build_select(
        self,
        ctx: RequestContext,
        *,
        columns: list[str] | None = None,
        filters: dict[str, dict[str, Any]] | None = None,
        sort: list[tuple[str, str]] | None = None,
        limit: int | None = None,
        offset: int | None = None,
        include_deleted: bool = False,
        pk_value: Any | None = None,
        for_count: bool = False,
    ) -> BoundQuery:
        args: list[Any] = []
        clauses: list[str] = []
        self.apply_row_filters(ctx, args, clauses)
        self.apply_soft_delete(clauses, include_deleted=include_deleted)
        if pk_value is not None:
            ph = self._next_arg(args, pk_value)
            clauses.append(f"{self._col(self.config.pk)} = {ph}")
        if filters:
            self.parse_filters(filters, args, clauses)

        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""

        if for_count:
            sql = f"SELECT COUNT(*) AS count FROM {self.table}{where}"
            return BoundQuery(sql, args)

        cols = columns or [c for c, f in self.config.fields.items() if f.read]
        select_list = ", ".join(self._col(c) for c in cols)
        sql = f"SELECT {select_list} FROM {self.table}{where}"

        if sort:
            parts = []
            sortable = set(self.config.sortable)
            for col, direction in sort:
                if col not in sortable:
                    raise ValidationAppError(f"field not sortable: {col}", code="SORT_DENIED")
                d = direction.upper()
                if d not in {"ASC", "DESC"}:
                    raise ValidationAppError(f"bad sort direction: {direction}", code="BAD_SORT")
                parts.append(f"{self._col(col)} {d}")
            sql += " ORDER BY " + ", ".join(parts)

        if limit is not None:
            sql += f" LIMIT {self._next_arg(args, limit)}"
        if offset is not None:
            sql += f" OFFSET {self._next_arg(args, offset)}"

        return BoundQuery(sql, args)

    def build_insert(self, columns: list[str], rows: list[dict[str, Any]]) -> BoundQuery:
        if not rows:
            raise ValidationAppError("empty insert", code="EMPTY_PAYLOAD")
        for col in columns:
            if col not in self.allowed:
                raise ValidationAppError(f"column not allowed: {col}", code="COLUMN_DENIED")
        col_sql = ", ".join(self._col(c) for c in columns)
        args: list[Any] = []
        value_groups = []
        for row in rows:
            placeholders = []
            for c in columns:
                placeholders.append(self._next_arg(args, row.get(c)))
            value_groups.append(f"({', '.join(placeholders)})")
        returning = ", ".join(self._col(c) for c in self.config.fields)
        sql = (
            f"INSERT INTO {self.table} ({col_sql}) VALUES {', '.join(value_groups)} "
            f"RETURNING {returning}"
        )
        return BoundQuery(sql, args)

    def build_update(
        self,
        ctx: RequestContext,
        pk_value: Any,
        values: dict[str, Any],
        *,
        include_deleted: bool = False,
    ) -> BoundQuery:
        if not values:
            raise ValidationAppError("empty update", code="EMPTY_PAYLOAD")
        args: list[Any] = []
        sets = []
        for col, val in values.items():
            sets.append(f"{self._col(col)} = {self._next_arg(args, val)}")
        clauses: list[str] = []
        self.apply_row_filters(ctx, args, clauses)
        self.apply_soft_delete(clauses, include_deleted=include_deleted)
        clauses.append(f"{self._col(self.config.pk)} = {self._next_arg(args, pk_value)}")
        where = " AND ".join(clauses)
        returning = ", ".join(self._col(c) for c in self.config.fields)
        sql = f"UPDATE {self.table} SET {', '.join(sets)} WHERE {where} RETURNING {returning}"
        return BoundQuery(sql, args)

    def build_soft_delete(self, ctx: RequestContext, pk_value: Any) -> BoundQuery:
        from datetime import datetime, timezone

        field = self.config.soft_delete.field
        return self.build_update(
            ctx,
            pk_value,
            {field: datetime.now(timezone.utc)},
            include_deleted=False,
        )

    def build_hard_delete(self, ctx: RequestContext, pk_value: Any) -> BoundQuery:
        args: list[Any] = []
        clauses: list[str] = []
        self.apply_row_filters(ctx, args, clauses)
        clauses.append(f"{self._col(self.config.pk)} = {self._next_arg(args, pk_value)}")
        where = " AND ".join(clauses)
        sql = f"DELETE FROM {self.table} WHERE {where} RETURNING {self._col(self.config.pk)}"
        return BoundQuery(sql, args)

    def build_bulk_delete(
        self,
        ctx: RequestContext,
        *,
        ids: list[Any] | None = None,
        filters: dict[str, dict[str, Any]] | None = None,
        soft: bool = False,
    ) -> BoundQuery:
        args: list[Any] = []
        clauses: list[str] = []
        self.apply_row_filters(ctx, args, clauses)
        if soft:
            self.apply_soft_delete(clauses, include_deleted=False)
        if ids:
            placeholders = [self._next_arg(args, i) for i in ids]
            clauses.append(f"{self._col(self.config.pk)} IN ({', '.join(placeholders)})")
        if filters:
            self.parse_filters(filters, args, clauses)
        if not ids and not filters:
            raise ValidationAppError(
                "bulk-delete requires ids and/or filters",
                code="EMPTY_BULK_DELETE",
            )
        where = " AND ".join(clauses)
        if soft:
            from datetime import datetime, timezone

            field = self.config.soft_delete.field
            returning = ", ".join(self._col(c) for c in self.config.fields)
            sql = (
                f"UPDATE {self.table} SET {self._col(field)} = "
                f"{self._next_arg(args, datetime.now(timezone.utc))} "
                f"WHERE {where} RETURNING {returning}"
            )
        else:
            sql = (
                f"DELETE FROM {self.table} WHERE {where} "
                f"RETURNING {self._col(self.config.pk)}"
            )
        return BoundQuery(sql, args)

    def build_upsert(
        self,
        columns: list[str],
        rows: list[dict[str, Any]],
        conflict_keys: list[str],
        update_columns: list[str],
    ) -> BoundQuery:
        if not conflict_keys:
            raise ValidationAppError("upsert_keys not configured", code="NO_UPSERT_KEYS")
        insert_q = self.build_insert(columns, rows)
        # rebuild with ON CONFLICT
        args = insert_q.args
        # extract VALUES portion from insert — rebuild cleanly
        args = []
        col_sql = ", ".join(self._col(c) for c in columns)
        value_groups = []
        for row in rows:
            placeholders = [self._next_arg(args, row.get(c)) for c in columns]
            value_groups.append(f"({', '.join(placeholders)})")
        conflict = ", ".join(self._col(c) for c in conflict_keys)
        if update_columns:
            sets = ", ".join(
                f"{self._col(c)} = EXCLUDED.{self._col(c)}" for c in update_columns
            )
            conflict_action = f"DO UPDATE SET {sets}"
        else:
            conflict_action = "DO NOTHING"
        returning = ", ".join(self._col(c) for c in self.config.fields)
        sql = (
            f"INSERT INTO {self.table} ({col_sql}) VALUES {', '.join(value_groups)} "
            f"ON CONFLICT ({conflict}) {conflict_action} RETURNING {returning}"
        )
        return BoundQuery(sql, args)

    def build_aggregate(
        self,
        ctx: RequestContext,
        *,
        function: str,
        field: str | None = None,
        group_by: list[str] | None = None,
        filters: dict[str, dict[str, Any]] | None = None,
        include_deleted: bool = False,
    ) -> BoundQuery:
        agg = self.config.aggregate
        fn = function.lower()
        if fn not in {f.lower() for f in agg.allowed_functions}:
            raise ValidationAppError(f"aggregate function not allowed: {function}", code="AGG_DENIED")

        args: list[Any] = []
        clauses: list[str] = []
        self.apply_row_filters(ctx, args, clauses)
        self.apply_soft_delete(clauses, include_deleted=include_deleted)
        if filters:
            self.parse_filters(filters, args, clauses)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""

        select_parts: list[str] = []
        group_cols = group_by or []
        for g in group_cols:
            if g not in agg.group_by:
                raise ValidationAppError(f"group_by not allowed: {g}", code="GROUP_DENIED")
            select_parts.append(self._col(g))

        if fn == "count":
            select_parts.append("COUNT(*) AS value")
        elif fn == "sum":
            if not field or field not in agg.sum_fields:
                raise ValidationAppError(f"sum field not allowed: {field}", code="SUM_DENIED")
            select_parts.append(f"SUM({self._col(field)}) AS value")
        else:
            raise ValidationAppError(f"unsupported aggregate: {fn}", code="AGG_DENIED")

        sql = f"SELECT {', '.join(select_parts)} FROM {self.table}{where}"
        if group_cols:
            sql += " GROUP BY " + ", ".join(self._col(g) for g in group_cols)
        return BoundQuery(sql, args)

    def build_related_select(
        self,
        related_config: ResourceConfig,
        *,
        foreign_col: str,
        local_values: list[Any],
        ctx: RequestContext,
        include_deleted: bool = False,
    ) -> BoundQuery:
        """Select related rows where foreign_col IN local_values."""
        qb = QueryBuilder("__related__", related_config)
        args: list[Any] = []
        clauses: list[str] = []
        qb.apply_row_filters(ctx, args, clauses)
        qb.apply_soft_delete(clauses, include_deleted=include_deleted)
        if not local_values:
            # empty IN — return no rows
            sql = f"SELECT {', '.join(qb._col(c) for c in related_config.fields)} FROM {qb.table} WHERE FALSE"
            return BoundQuery(sql, [])
        placeholders = [qb._next_arg(args, v) for v in local_values]
        clauses.append(f"{qb._col(foreign_col)} IN ({', '.join(placeholders)})")
        where = " AND ".join(clauses)
        cols = ", ".join(qb._col(c) for c in related_config.fields)
        sql = f"SELECT {cols} FROM {qb.table} WHERE {where}"
        return BoundQuery(sql, args)


def parse_sort_param(sort: str | None) -> list[tuple[str, str]]:
    if not sort:
        return []
    result = []
    for part in sort.split(","):
        part = part.strip()
        if not part:
            continue
        if part.startswith("-"):
            result.append((part[1:], "DESC"))
        elif part.startswith("+"):
            result.append((part[1:], "ASC"))
        else:
            result.append((part, "ASC"))
    return result


def coerce_pk(value: str) -> Any:
    """Try UUID then int then string for path id."""
    try:
        return UUID(value)
    except (ValueError, AttributeError):
        pass
    try:
        return int(value)
    except ValueError:
        return value
