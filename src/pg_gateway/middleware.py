from __future__ import annotations

import json
from uuid import uuid4

from starlette.types import ASGIApp, Receive, Scope, Send

from pg_gateway.config.models import AuthzConfig
from pg_gateway.context import RequestContext, clear_request_context, set_request_context


# Paths that skip the header_stub trust gate (no tenant/roles required).
_PUBLIC_PATHS = frozenset({"/health"})


class RequestContextMiddleware:
    """Pure ASGI middleware (avoids BaseHTTPMiddleware event-loop issues)."""

    def __init__(
        self,
        app: ASGIApp,
        authz: AuthzConfig,
        *,
        trust_token: str = "",
        known_roles: frozenset[str] | None = None,
    ) -> None:
        self.app = app
        self.authz = authz
        self.trust_token = trust_token
        self.known_roles = known_roles or frozenset()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}
        path = scope.get("path", "") or ""
        request_id = headers.get("x-request-id") or str(uuid4())
        public = path.rstrip("/") in _PUBLIC_PATHS or path in _PUBLIC_PATHS

        trusted = False
        tenant: str | None = None
        roles: tuple[str, ...] = ()

        if self.authz.mode == "header_stub" and not public:
            provided = headers.get(self.authz.trust_header.lower(), "")
            if not self.trust_token or provided != self.trust_token:
                await self._send_json(
                    send,
                    status=401,
                    body={"detail": "missing or invalid gateway trust token", "code": "UNAUTHORIZED"},
                    request_id=request_id,
                )
                return
            trusted = True
            tenant = headers.get(self.authz.tenant_header.lower())
            roles_raw = headers.get(self.authz.roles_header.lower(), "")
            raw_roles = tuple(r.strip() for r in roles_raw.split(",") if r.strip())
            # Fail-closed unknown roles: drop names not in any resource registry.
            roles = tuple(r for r in raw_roles if r in self.known_roles)

        set_request_context(
            RequestContext(
                tenant_id=tenant,
                roles=roles,
                request_id=request_id,
                trusted=trusted or public,
            )
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

    @staticmethod
    async def _send_json(
        send: Send,
        *,
        status: int,
        body: dict,
        request_id: str,
    ) -> None:
        payload = json.dumps(body).encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(payload)).encode("ascii")),
                    (b"x-request-id", request_id.encode("latin-1")),
                ],
            }
        )
        await send({"type": "http.response.body", "body": payload})
