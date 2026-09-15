from __future__ import annotations

from pg_gateway.config.models import ResourceConfig, RoleAccess
from pg_gateway.context import RequestContext
from pg_gateway.errors import ForbiddenError


class ACLChecker:
    """Role-based ACL from resource config."""

    def __init__(self, resource_name: str, config: ResourceConfig) -> None:
        self.resource_name = resource_name
        self.config = config

    def _matching_roles(self, ctx: RequestContext) -> list[tuple[str, RoleAccess]]:
        return [(name, role) for name, role in self.config.roles.items() if name in ctx.roles]

    def require_operation(self, ctx: RequestContext, operation: str) -> None:
        # Map API ops to OperationsConfig flags
        ops = self.config.operations
        flag_map = {
            "list": ops.list,
            "get": ops.get,
            "create": ops.create,
            "update": ops.update,
            "patch": ops.patch,
            "delete": ops.delete,
            "batch_create": ops.batch_create,
            "bulk_delete": ops.bulk_delete,
            "upsert": ops.upsert,
            "aggregate": ops.aggregate,
        }
        if not flag_map.get(operation, False):
            raise ForbiddenError(
                f"operation '{operation}' disabled for resource '{self.resource_name}'",
                code="OPERATION_DISABLED",
            )

        matches = self._matching_roles(ctx)
        if not self.config.roles:
            # No roles configured → allow if operation enabled
            return
        if not ctx.roles:
            raise ForbiddenError("missing roles", code="MISSING_ROLES")
        if not matches:
            raise ForbiddenError(
                f"roles {list(ctx.roles)} not permitted for '{self.resource_name}'",
                code="ROLE_DENIED",
            )
        for _, role in matches:
            if role.operations is None or operation in role.operations:
                return
        raise ForbiddenError(
            f"operation '{operation}' not allowed for roles {list(ctx.roles)}",
            code="OPERATION_DENIED",
        )

    def readable_fields(self, ctx: RequestContext) -> set[str]:
        base = {n for n, f in self.config.fields.items() if f.read}
        matches = self._matching_roles(ctx)
        if not self.config.roles or not matches:
            return base
        allowed: set[str] | None = None
        for _, role in matches:
            if role.fields is None or role.fields.read is None:
                return base
            fields = set(role.fields.read) & base
            allowed = fields if allowed is None else allowed | fields
        return allowed or set()

    def writable_fields(self, ctx: RequestContext, *, for_create: bool = False) -> set[str]:
        base = {
            n
            for n, f in self.config.fields.items()
            if f.write and not f.primary_key and not f.auto
        }
        matches = self._matching_roles(ctx)
        if not self.config.roles or not matches:
            return base
        allowed: set[str] | None = None
        for _, role in matches:
            if role.fields is None or role.fields.write is None:
                return base
            fields = set(role.fields.write) & base
            allowed = fields if allowed is None else allowed | fields
        return allowed or set()

    def filter_read_payload(self, ctx: RequestContext, row: dict) -> dict:
        allowed = self.readable_fields(ctx)
        return {k: v for k, v in row.items() if k in allowed}

    def filter_write_payload(self, ctx: RequestContext, payload: dict) -> dict:
        allowed = self.writable_fields(ctx)
        unknown = set(payload) - allowed - {self.config.pk}
        # PK may appear in upsert payloads; strip auto/pk write attempts
        filtered = {k: v for k, v in payload.items() if k in allowed}
        # Also allow writing row-filter context columns if declared writable in fields
        return filtered
