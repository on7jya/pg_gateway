from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from pg_gateway.config import Settings, load_config
from pg_gateway.main import create_app
from tests.conftest import CONFIG_PATH, ROOT

pytestmark = pytest.mark.integration

ACCOUNTS_PATH = ROOT / "config" / "accounts.example.yaml"
ORDERS_READER_DN = "CN=orders-reader,OU=tuz,O=Acme,C=RU"
USERS_ADMIN_DN = "CN=users-admin,OU=tuz,O=Acme,C=RU"


@pytest.fixture
def cert_dn_config():
    return load_config(CONFIG_PATH, accounts_path=ACCOUNTS_PATH)


@pytest.mark.asyncio
async def test_cert_dn_orders_reader_list_allowed(cert_dn_config, database_url):
    """Known DN with grant passes auth; RLS may still return empty without tenant."""
    settings = Settings(
        config_path=str(CONFIG_PATH),
        database_url=database_url,
        gateway_trust_token="",
    )
    app = create_app(config=cert_dn_config, settings=settings, connect_db=True)
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get(
                "/api/v1/orders",
                headers={"X-Client-Cert-DN": ORDERS_READER_DN},
            )
            assert r.status_code == 200
            body = r.json()
            assert "data" in body
            assert isinstance(body["data"], list)


@pytest.mark.asyncio
async def test_cert_dn_orders_reader_users_denied(cert_dn_config, database_url):
    settings = Settings(
        config_path=str(CONFIG_PATH),
        database_url=database_url,
        gateway_trust_token="",
    )
    app = create_app(config=cert_dn_config, settings=settings, connect_db=True)
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get(
                "/api/v1/users",
                headers={
                    "X-Client-Cert-DN": ORDERS_READER_DN,
                    "X-Roles": "admin",
                    "X-Tenant-Id": "11111111-1111-1111-1111-111111111111",
                },
            )
            assert r.status_code == 403
            assert r.json()["code"] == "AUTHZ_DENIED"


@pytest.mark.asyncio
async def test_cert_dn_users_admin_list_users(cert_dn_config, database_url):
    settings = Settings(
        config_path=str(CONFIG_PATH),
        database_url=database_url,
        gateway_trust_token="",
    )
    app = create_app(config=cert_dn_config, settings=settings, connect_db=True)
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get(
                "/api/v1/users",
                headers={"X-Client-Cert-DN": USERS_ADMIN_DN},
            )
            assert r.status_code == 200
            assert "data" in r.json()
