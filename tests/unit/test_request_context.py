from __future__ import annotations

import pytest

from pg_gateway.config.models import AuthzConfig
from pg_gateway.context import RequestContext, get_request_context
from pg_gateway.middleware import RequestContextMiddleware

DN = "CN=x,O=Acme,C=RU"
TENANT = "11111111-1111-1111-1111-111111111111"


class _CaptureApp:
    def __init__(self) -> None:
        self.ctx: RequestContext | None = None

    async def __call__(self, scope, receive, send) -> None:
        self.ctx = get_request_context()


def _http_scope(path: str, headers: dict[str, str]) -> dict:
    return {
        "type": "http",
        "path": path,
        "headers": [
            (k.lower().encode("latin-1"), v.encode("latin-1")) for k, v in headers.items()
        ],
    }


async def _receive():
    return {"type": "http.request", "body": b"", "more_body": False}


async def _send(message):
    pass


def _middleware(app: _CaptureApp) -> RequestContextMiddleware:
    authz = AuthzConfig()
    return RequestContextMiddleware(app, authz, account_tenants={DN: TENANT})


def _base_headers() -> dict[str, str]:
    return {"X-Client-Cert-DN": DN}


@pytest.mark.asyncio
async def test_tenant_injected_from_account():
    app = _CaptureApp()
    mw = _middleware(app)
    await mw(_http_scope("/api/v1/users", _base_headers()), _receive, _send)
    assert app.ctx is not None
    assert app.ctx.tenant_id == TENANT
    assert app.ctx.account_dn == DN


@pytest.mark.asyncio
async def test_both_optional_headers_captured():
    app = _CaptureApp()
    mw = _middleware(app)
    headers = {**_base_headers(), "X-Session-Id": "sess-123", "X-User-Id": "user-456"}
    await mw(_http_scope("/api/v1/users", headers), _receive, _send)
    assert app.ctx is not None
    assert app.ctx.session_id == "sess-123"
    assert app.ctx.user_id == "user-456"


@pytest.mark.asyncio
async def test_only_session_header_captured():
    app = _CaptureApp()
    mw = _middleware(app)
    headers = {**_base_headers(), "X-Session-Id": "sess-1"}
    await mw(_http_scope("/api/v1/users", headers), _receive, _send)
    assert app.ctx.session_id == "sess-1"
    assert app.ctx.user_id is None


@pytest.mark.asyncio
async def test_only_user_header_captured():
    app = _CaptureApp()
    mw = _middleware(app)
    headers = {**_base_headers(), "X-User-Id": "user-1"}
    await mw(_http_scope("/api/v1/users", headers), _receive, _send)
    assert app.ctx.session_id is None
    assert app.ctx.user_id == "user-1"


@pytest.mark.asyncio
async def test_no_optional_headers_none():
    app = _CaptureApp()
    mw = _middleware(app)
    await mw(_http_scope("/api/v1/users", _base_headers()), _receive, _send)
    assert app.ctx.session_id is None
    assert app.ctx.user_id is None


@pytest.mark.asyncio
async def test_blank_optional_headers_are_none():
    app = _CaptureApp()
    mw = _middleware(app)
    headers = {**_base_headers(), "X-Session-Id": "   ", "X-User-Id": ""}
    await mw(_http_scope("/api/v1/users", headers), _receive, _send)
    assert app.ctx.session_id is None
    assert app.ctx.user_id is None


@pytest.mark.asyncio
async def test_unknown_dn_401():
    app = _CaptureApp()
    mw = _middleware(app)
    status = {}

    async def send(message):
        if message["type"] == "http.response.start":
            status["status"] = message["status"]

    await mw(
        _http_scope("/api/v1/users", {"X-Client-Cert-DN": "CN=ghost,O=Acme,C=RU"}),
        _receive,
        send,
    )
    assert status["status"] == 401
    assert app.ctx is None
