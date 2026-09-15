from __future__ import annotations

from uuid import uuid4

from starlette.types import ASGIApp, Receive, Scope, Send

from pg_gateway.config.models import AuthzConfig
from pg_gateway.context import RequestContext, clear_request_context, set_request_context


class RequestContextMiddleware:
    """Pure ASGI middleware (avoids BaseHTTPMiddleware event-loop issues)."""

    def __init__(self, app: ASGIApp, authz: AuthzConfig) -> None:
        self.app = app
        self.authz = authz

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}
        tenant = headers.get(self.authz.tenant_header.lower())
        roles_raw = headers.get(self.authz.roles_header.lower(), "")
        roles = tuple(r.strip() for r in roles_raw.split(",") if r.strip())
        request_id = headers.get("x-request-id") or str(uuid4())
        set_request_context(
            RequestContext(tenant_id=tenant, roles=roles, request_id=request_id)
        )

        async def send_wrapper(message: dict) -> None:
            if message["type"] == "http.response.start":
                raw_headers = list(message.get("headers", []))
                raw_headers.append((b"x-request-id", request_id.encode("latin-1")))
                message = {**message, "headers": raw_headers}
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            clear_request_context()
