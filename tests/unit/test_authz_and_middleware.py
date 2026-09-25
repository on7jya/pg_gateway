from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from pg_gateway.authz import DenyAllAuthz
from pg_gateway.config import Settings, load_config
from pg_gateway.context import RequestContext
from pg_gateway.main import create_app
from tests.conftest import ACCOUNTS_PATH, CONFIG_PATH, ORDERS_READER_DN


@pytest.mark.asyncio
async def test_deny_all_authz_port():
    authz = DenyAllAuthz()
    ctx = RequestContext(account_dn=ORDERS_READER_DN, trusted=True)
    assert await authz.allow(ctx, "orders", "list") is False


def _cert_dn_app():
    settings = Settings(
        config_path=str(CONFIG_PATH),
        database_url="postgresql://x",
        accounts_config_path=str(ACCOUNTS_PATH),
    )
    app = create_app(
        config=load_config(CONFIG_PATH, accounts_path=ACCOUNTS_PATH),
        settings=settings,
        connect_db=False,
    )
    return app


@pytest.mark.asyncio
async def test_unknown_dn_401_on_api():
    app = _cert_dn_app()
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get(
                "/api/v1/orders",
                headers={"X-Client-Cert-DN": "CN=ghost,O=Acme,C=RU"},
            )
            assert r.status_code == 401
            assert r.json()["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_health_open_without_dn():
    app = _cert_dn_app()
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get("/health")
            assert r.status_code == 200
            assert r.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_ready_requires_dn():
    app = _cert_dn_app()
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get("/ready")
            assert r.status_code == 401
            assert r.json()["code"] == "UNAUTHORIZED"


def test_create_app_requires_accounts():
    settings = Settings(config_path=str(CONFIG_PATH), database_url="postgresql://x")
    with pytest.raises(RuntimeError, match="account"):
        create_app(config=load_config(CONFIG_PATH), settings=settings, connect_db=False)
