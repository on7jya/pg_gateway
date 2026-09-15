from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from pg_gateway.authz import DenyAllAuthz, HeaderStubAuthz
from pg_gateway.config import Settings, load_config
from pg_gateway.context import RequestContext
from pg_gateway.main import _known_roles, create_app
from tests.conftest import CONFIG_PATH, TENANT_A, TRUST_TOKEN, gateway_headers


@pytest.mark.asyncio
async def test_deny_all_authz_port():
    authz = DenyAllAuthz()
    ctx = RequestContext(tenant_id=TENANT_A, roles=("admin",), trusted=True)
    assert await authz.allow(ctx, "users", "list") is False


@pytest.mark.asyncio
async def test_header_stub_unknown_resource(app_config):
    authz = HeaderStubAuthz(app_config)
    ctx = RequestContext(tenant_id=TENANT_A, roles=("admin",), trusted=True)
    assert await authz.allow(ctx, "does_not_exist", "list") is False


@pytest.mark.asyncio
async def test_header_stub_reader_trusted(app_config):
    authz = HeaderStubAuthz(app_config)
    ctx = RequestContext(tenant_id=TENANT_A, roles=("reader",), trusted=True)
    assert await authz.allow(ctx, "users", "list") is True
    # Fine-grained op denial is ACL's job; port only checks role membership.
    assert await authz.allow(ctx, "users", "create") is True


def test_known_roles_registry(app_config):
    known = _known_roles(app_config)
    assert known == frozenset({"admin", "reader"})
    assert "ghost" not in known


@pytest.mark.asyncio
async def test_wrong_trust_token_401_on_api():
    settings = Settings(
        config_path=str(CONFIG_PATH),
        database_url="postgresql://x",
        gateway_trust_token=TRUST_TOKEN,
    )
    app = create_app(config=load_config(CONFIG_PATH), settings=settings, connect_db=False)
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get(
                "/api/v1/users",
                headers=gateway_headers(token="wrong-token"),
            )
            assert r.status_code == 401
            assert r.json()["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_health_open_without_token():
    settings = Settings(
        config_path=str(CONFIG_PATH),
        database_url="postgresql://x",
        gateway_trust_token=TRUST_TOKEN,
    )
    app = create_app(config=load_config(CONFIG_PATH), settings=settings, connect_db=False)
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get("/health")
            assert r.status_code == 200
            assert r.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_ready_requires_trust_token():
    settings = Settings(
        config_path=str(CONFIG_PATH),
        database_url="postgresql://x",
        gateway_trust_token=TRUST_TOKEN,
    )
    app = create_app(config=load_config(CONFIG_PATH), settings=settings, connect_db=False)
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get("/ready")
            assert r.status_code == 401
            assert r.json()["code"] == "UNAUTHORIZED"
