from __future__ import annotations

from pg_gateway.config.models import ResourceConfig, RoleAccess
from pg_gateway.context import RequestContext
from pg_gateway.errors import ForbiddenError


class ACLChecker:
    """ACL from resource role config or technical-account grants."""

    def __init__(
        self,
        resource_name: str,
        config: ResourceConfig,
        *,
        account_grant: RoleAccess | None = None,
        account_mode: bool = False,
    ) -> None:
        self.resource_name = resource_name
        self.config = config
        self.account_grant = account_grant
        self.account_mode = account_mode

    def _matching_roles(self, ctx: RequestContext) -> list[tuple[str, RoleAccess]]:
        return [(name, role) for name, role in self.config.roles.items() if name in ctx.roles]

    def _operation_enabled(self, operation: str) -> None:
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

    def require_operation(self, ctx: RequestContext, operation: str) -> None:
        self._operation_enabled(operation)

        if self.account_mode:
            if self.account_grant is None:
                raise ForbiddenError(
                    f"account has no grant for resource '{self.resource_name}'",
                    code="GRANT_DENIED",
                )
            grant = self.account_grant
            if grant.operations is None or operation in grant.operations:
                return
            raise ForbiddenError(
                f"operation '{operation}' not allowed for account grant on '{self.resource_name}'",
                code="OPERATION_DENIED",
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
        if self.account_mode:
            if self.account_grant is None:
                return set()
            grant = self.account_grant
            if grant.fields is None or grant.fields.read is None:
                return base
            return set(grant.fields.read) & base

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

    def writable_fields(self, ctx: RequestContext) -> set[str]:
        base = {
            n
            for n, f in self.config.fields.items()
            if f.write and not f.primary_key and not f.auto
        }
        if self.account_mode:
            if self.account_grant is None:
                return set()
            grant = self.account_grant
            if grant.fields is None or grant.fields.write is None:
                return base
            return set(grant.fields.write) & base

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
