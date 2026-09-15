"""Authorization port — stub for future external authz integration."""

from __future__ import annotations

from abc import ABC, abstractmethod

from pg_gateway.config.models import AppConfig
from pg_gateway.context import RequestContext


class AuthzPort(ABC):
    """Abstract authorization decision port."""

    @abstractmethod
    async def allow(
        self,
        ctx: RequestContext,
        resource: str,
        operation: str,
        *,
        field: str | None = None,
        action: str | None = None,
    ) -> bool:
        """Return True if the request is permitted."""


class HeaderStubAuthz(AuthzPort):
    """
    Safe-by-default header stub for demos.

    Trust is established by middleware via GATEWAY_TRUST_TOKEN.
    This port verifies trust + that at least one claimed role exists on the
    resource when roles are configured. Fine-grained ACL remains in ACLChecker.
    """

    def __init__(self, config: AppConfig) -> None:
        self.config = config

    async def allow(
        self,
        ctx: RequestContext,
        resource: str,
        operation: str,
        *,
        field: str | None = None,
        action: str | None = None,
    ) -> bool:
        if not ctx.trusted:
            return False
        try:
            rc = self.config.resource(resource)
        except KeyError:
            return False
        if not rc.roles:
            return True
        if not ctx.roles:
            return False
        return any(role in rc.roles for role in ctx.roles)


class DenyAllAuthz(AuthzPort):
    async def allow(
        self,
        ctx: RequestContext,
        resource: str,
        operation: str,
        *,
        field: str | None = None,
        action: str | None = None,
    ) -> bool:
        return False
