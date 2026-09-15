"""Authorization port — stub for future external authz integration."""

from __future__ import annotations

from abc import ABC, abstractmethod

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
    v1 stub: trust headers already parsed into RequestContext.
    Actual ACL decisions are handled by ACLChecker using config roles.
    This port always returns True so ACL remains the gate.
    """

    async def allow(
        self,
        ctx: RequestContext,
        resource: str,
        operation: str,
        *,
        field: str | None = None,
        action: str | None = None,
    ) -> bool:
        return True


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
