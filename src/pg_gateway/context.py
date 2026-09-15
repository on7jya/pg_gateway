from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field


@dataclass(frozen=True)
class RequestContext:
    tenant_id: str | None = None
    roles: tuple[str, ...] = field(default_factory=tuple)
    request_id: str | None = None
    trusted: bool = False

    def has_role(self, role: str) -> bool:
        return role in self.roles

    def has_any_role(self, roles: list[str] | tuple[str, ...]) -> bool:
        return any(r in self.roles for r in roles)


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
