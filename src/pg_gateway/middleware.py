from __future__ import annotations

import json
from uuid import uuid4

from starlette.types import ASGIApp, Receive, Scope, Send

from pg_gateway.config.models import AuthzConfig
from pg_gateway.context import RequestContext, clear_request_context, set_request_context

# Paths that skip the DN gate (no account DN required).
_PUBLIC_PATHS = frozenset({"/health"})


class RequestContextMiddleware:
    """Pure ASGI middleware (avoids BaseHTTPMiddleware event-loop issues)."""

    def __init__(
        self,
        app: ASGIApp,
        authz: AuthzConfig,
        *,
        account_tenants: dict[str, str] | None = None,
    ) -> None:
        self.app = app
        self.authz = authz
        self.account_tenants = account_tenants or {}

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = {
            k.decode("latin-1").lower(): v.decode("latin-1")
            for k, v in scope.get("headers", [])
        }
        path = scope.get("path", "") or ""
        request_id = headers.get("x-request-id") or str(uuid4())
        session_id = self._optional_header(headers, self.authz.session_id_header)
        user_id = self._optional_header(headers, self.authz.user_id_header)
        public = path.rstrip("/") in _PUBLIC_PATHS or path in _PUBLIC_PATHS

        trusted = False
        tenant: str | None = None
        account_dn: str | None = None

        if not public:
            dn = headers.get(self.authz.client_dn_header.lower(), "").strip()
            if not dn or dn not in self.account_tenants:
                await self._send_json(
                    send,
                    status=401,
                    body={
                        "detail": "missing or unknown client certificate DN",
                        "code": "UNAUTHORIZED",
                    },
                    request_id=request_id,
                )
                return
            trusted = True
            account_dn = dn
            tenant = self.account_tenants[dn]

        set_request_context(
            RequestContext(
                tenant_id=tenant,
                account_dn=account_dn,
                session_id=session_id,
                user_id=user_id,
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
    def _optional_header(headers: dict[str, str], name: str) -> str | None:
        """Return a trimmed optional header value, or None if absent/blank."""
        value = headers.get(name.lower(), "")
        return value.strip() or None

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
