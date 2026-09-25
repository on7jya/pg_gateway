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


class CertDnAuthz(AuthzPort):
    """
    Certificate DN technical-account authorization.

    Trust/identity: middleware validated X-Client-Cert-DN against accounts.
    Allow iff the account has a grant entry for the resource. Fine-grained
    ops/fields remain in ACLChecker.
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
        if not ctx.trusted or not ctx.account_dn:
            return False
        if resource not in self.config.resources:
            return False
        account = self.config.account(ctx.account_dn)
        if account is None:
            return False
        return resource in account.grants


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
