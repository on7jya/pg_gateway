from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from pg_gateway.acl import ACLChecker
from pg_gateway.authz import CertDnAuthz
from pg_gateway.config import Settings, load_config
from pg_gateway.context import RequestContext
from pg_gateway.errors import ForbiddenError
from pg_gateway.main import create_app
from tests.conftest import ACCOUNTS_PATH, CONFIG_PATH

ORDERS_READER_DN = "CN=orders-reader,OU=tuz,O=Acme,C=RU"
USERS_ADMIN_DN = "CN=users-admin,OU=tuz,O=Acme,C=RU"


@pytest.fixture(scope="module")
def cert_dn_config():
    return load_config(CONFIG_PATH, accounts_path=ACCOUNTS_PATH)


def test_accounts_overlay_sets_cert_dn(cert_dn_config):
    assert cert_dn_config.authz.client_dn_header == "X-Client-Cert-DN"
    assert ORDERS_READER_DN in cert_dn_config.accounts
    assert USERS_ADMIN_DN in cert_dn_config.accounts
    # tenant filter restored — tenant now comes from account
    assert cert_dn_config.resources["orders"].row_filters != []


def test_accounts_have_tenant_id(cert_dn_config):
    account = cert_dn_config.accounts[ORDERS_READER_DN]
    assert account.tenant_id == "11111111-1111-1111-1111-111111111111"
    assert account.grants["orders"].operations is not None


def test_dn_keys_are_trimmed():
    from pg_gateway.config.models import AppConfig

    raw = load_config(CONFIG_PATH, accounts_path=ACCOUNTS_PATH)
    data = raw.model_dump()
    padded = f"  {ORDERS_READER_DN}  "
    data["accounts"] = {padded: data["accounts"][ORDERS_READER_DN]}
    cfg = AppConfig.model_validate(data)
    assert ORDERS_READER_DN in cfg.accounts
    assert padded not in cfg.accounts


def test_grant_unknown_resource_rejected():
    from pg_gateway.config.models import AppConfig

    base = load_config(CONFIG_PATH).model_dump()
    base["accounts"] = {
        "CN=x": {
            "tenant_id": "11111111-1111-1111-1111-111111111111",
            "grants": {"no_such_resource": {"operations": ["list"]}},
        },
    }
    with pytest.raises(ValidationError, match="not a known resource"):
        AppConfig.model_validate(base)


def test_account_requires_tenant_id():
    from pg_gateway.config.models import AppConfig

    base = load_config(CONFIG_PATH).model_dump()
    base["accounts"] = {
        "CN=x": {"grants": {"users": {"operations": ["list"]}}},
    }
    with pytest.raises(ValidationError, match="tenant_id"):
        AppConfig.model_validate(base)


@pytest.mark.asyncio
async def test_cert_dn_authz_allow_and_deny(cert_dn_config):
    authz = CertDnAuthz(cert_dn_config)
    ctx = RequestContext(account_dn=ORDERS_READER_DN, trusted=True)
    assert await authz.allow(ctx, "orders", "list") is True
    assert await authz.allow(ctx, "order_items", "list") is True
    assert await authz.allow(ctx, "users", "list") is False
    untrusted = RequestContext(account_dn=ORDERS_READER_DN, trusted=False)
    assert await authz.allow(untrusted, "orders", "list") is False


def test_acl_account_grant_ops_and_fields(cert_dn_config):
    grant = cert_dn_config.accounts[ORDERS_READER_DN].grants["orders"]
    acl = ACLChecker("orders", cert_dn_config.resource("orders"), account_grant=grant)
    ctx = RequestContext(account_dn=ORDERS_READER_DN, trusted=True)
    acl.require_operation(ctx, "list")
    with pytest.raises(ForbiddenError) as ei:
        acl.require_operation(ctx, "create")
    assert ei.value.code == "OPERATION_DENIED"
    readable = acl.readable_fields(ctx)
    assert "order_number" in readable
    assert "tenant_id" in readable
    assert "deleted_at" not in readable
    assert acl.writable_fields(ctx) == set()


def test_acl_account_mode_no_grant(cert_dn_config):
    acl = ACLChecker("users", cert_dn_config.resource("users"), account_grant=None)
    ctx = RequestContext(account_dn=ORDERS_READER_DN, trusted=True)
    with pytest.raises(ForbiddenError) as ei:
        acl.require_operation(ctx, "list")
    assert ei.value.code == "GRANT_DENIED"


def _app(cert_dn_config):
    settings = Settings(
        config_path=str(CONFIG_PATH),
        database_url="postgresql://x",
        accounts_config_path=str(ACCOUNTS_PATH),
    )
    return create_app(config=cert_dn_config, settings=settings, connect_db=False)


def test_cert_dn_openapi_scheme(cert_dn_config):
    app = _app(cert_dn_config)
    schema = app.openapi()
    assert "ClientCertDN" in schema["components"]["securitySchemes"]
    assert schema["security"] == [{"ClientCertDN": []}]
    assert "GatewayToken" not in schema["components"]["securitySchemes"]


@pytest.mark.asyncio
async def test_cert_dn_missing_header_401(cert_dn_config):
    app = _app(cert_dn_config)
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get("/api/v1/orders")
            assert r.status_code == 401
            assert r.json()["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_cert_dn_unknown_dn_401(cert_dn_config):
    app = _app(cert_dn_config)
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get(
                "/api/v1/orders",
                headers={"X-Client-Cert-DN": "CN=unknown,O=Acme,C=RU"},
            )
            assert r.status_code == 401
            assert r.json()["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_cert_dn_deny_other_resource_403(cert_dn_config):
    app = _app(cert_dn_config)
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get(
                "/api/v1/users",
                headers={"X-Client-Cert-DN": ORDERS_READER_DN},
            )
            assert r.status_code == 403
            assert r.json()["code"] == "AUTHZ_DENIED"


@pytest.mark.asyncio
async def test_cert_dn_ignores_roles_and_tenant_headers(cert_dn_config):
    """Roles/Tenant headers must not grant access beyond DN grants."""
    app = _app(cert_dn_config)
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
async def test_cert_dn_health_open(cert_dn_config):
    app = _app(cert_dn_config)
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get("/health")
            assert r.status_code == 200
