from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass


@dataclass(frozen=True)
class RequestContext:
    tenant_id: str | None = None
    account_dn: str | None = None
    session_id: str | None = None
    user_id: str | None = None
    request_id: str | None = None
    trusted: bool = False


_ctx: ContextVar[RequestContext | None] = ContextVar("request_context", default=None)


def set_request_context(ctx: RequestContext) -> None:
    _ctx.set(ctx)


def get_request_context() -> RequestContext:
    ctx = _ctx.get()
    if ctx is None:
        return RequestContext()
    return ctx


def clear_request_context() -> None:
    _ctx.set(None)
