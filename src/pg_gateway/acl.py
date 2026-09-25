from __future__ import annotations

from pg_gateway.config.models import ResourceConfig, RoleAccess
from pg_gateway.context import RequestContext
from pg_gateway.errors import ForbiddenError


class ACLChecker:
    """ACL from technical-account grants (cert_dn)."""

    def __init__(
        self,
        resource_name: str,
        config: ResourceConfig,
        *,
        account_grant: RoleAccess | None = None,
    ) -> None:
        self.resource_name = resource_name
        self.config = config
        self.account_grant = account_grant

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
        grant = self.account_grant
        if grant is None:
            raise ForbiddenError(
                f"account has no grant for resource '{self.resource_name}'",
                code="GRANT_DENIED",
            )
        if grant.operations is None or operation in grant.operations:
            return
        raise ForbiddenError(
            f"operation '{operation}' not allowed for account grant on '{self.resource_name}'",
            code="OPERATION_DENIED",
        )

    def readable_fields(self, ctx: RequestContext) -> set[str]:
        base = {n for n, f in self.config.fields.items() if f.read}
        grant = self.account_grant
        if grant is None:
            return set()
        if grant.fields is None or grant.fields.read is None:
            return base
        return set(grant.fields.read) & base

    def writable_fields(self, ctx: RequestContext) -> set[str]:
        base = {
            n
            for n, f in self.config.fields.items()
            if f.write and not f.primary_key and not f.auto
        }
        grant = self.account_grant
        if grant is None:
            return set()
        if grant.fields is None or grant.fields.write is None:
            return base
        return set(grant.fields.write) & base

    def filter_read_payload(self, ctx: RequestContext, row: dict) -> dict:
        allowed = self.readable_fields(ctx)
        return {k: v for k, v in row.items() if k in allowed}
