from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from pg_gateway.config import Settings, load_config
from pg_gateway.main import create_app
from tests.conftest import ACCOUNTS_PATH, ADMIN_DN, CONFIG_PATH

pytestmark = pytest.mark.integration

ORDERS_READER_DN = "CN=orders-reader,OU=tuz,O=Acme,C=RU"
USERS_ADMIN_DN = "CN=users-admin,OU=tuz,O=Acme,C=RU"
TENANT_B_READER_DN = "CN=tenant-b-reader,OU=tuz,O=Acme,C=RU"


@pytest.fixture
def cert_dn_config():
    return load_config(CONFIG_PATH, accounts_path=ACCOUNTS_PATH)


def _settings(database_url: str) -> Settings:
    return Settings(
        config_path=str(CONFIG_PATH),
        database_url=database_url,
        accounts_config_path=str(ACCOUNTS_PATH),
    )


@pytest.mark.asyncio
async def test_cert_dn_orders_reader_list_allowed(cert_dn_config, database_url):
    """Known DN with grant passes auth; tenant comes from account (RLS active)."""
    app = create_app(config=cert_dn_config, settings=_settings(database_url), connect_db=True)
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
    app = create_app(config=cert_dn_config, settings=_settings(database_url), connect_db=True)
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
    app = create_app(config=cert_dn_config, settings=_settings(database_url), connect_db=True)
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get(
                "/api/v1/users",
                headers={"X-Client-Cert-DN": USERS_ADMIN_DN},
            )
            assert r.status_code == 200
            assert "data" in r.json()


@pytest.mark.asyncio
async def test_tenant_isolation_between_accounts(cert_dn_config, database_url):
    """Account on tenant A sees A's rows; account on tenant B sees B's rows."""
    app = create_app(config=cert_dn_config, settings=_settings(database_url), connect_db=True)
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r_a = await client.get(
                "/api/v1/users",
                headers={"X-Client-Cert-DN": ADMIN_DN},
            )
            assert r_a.status_code == 200
            emails_a = {u["email"] for u in r_a.json()["data"]}
            assert "alice@acme.test" in emails_a
            assert "carol@other.test" not in emails_a

            r_b = await client.get(
                "/api/v1/users",
                headers={"X-Client-Cert-DN": TENANT_B_READER_DN},
            )
            assert r_b.status_code == 200
            emails_b = {u["email"] for u in r_b.json()["data"]}
            assert "carol@other.test" in emails_b
            assert "alice@acme.test" not in emails_b
