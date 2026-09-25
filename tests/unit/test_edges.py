"""Edge/error-path tests for config, models, builder, ACL, authz, service, db."""

from __future__ import annotations

from uuid import UUID

import pytest
from pydantic import ValidationError

from pg_gateway.acl import ACLChecker
from pg_gateway.authz import CertDnAuthz
from pg_gateway.config import Settings, load_config
from pg_gateway.config.loader import load_yaml, merge_accounts_overlay
from pg_gateway.config.models import AppConfig, RoleAccess
from pg_gateway.context import RequestContext, clear_request_context, get_request_context
from pg_gateway.db import Database
from pg_gateway.errors import (
    ForbiddenError,
    NotFoundError,
    error_body,
)
from pg_gateway.middleware import RequestContextMiddleware
from pg_gateway.service import ResourceService
from pg_gateway.sql.builder import QueryBuilder, coerce_pk
from tests.conftest import ACCOUNTS_PATH, CONFIG_PATH, ORDERS_READER_DN, TENANT_A

# ---------------------------------------------------------------- loader


def test_load_yaml_non_mapping(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("- item\n", encoding="utf-8")
    with pytest.raises(ValueError, match="mapping"):
        load_yaml(bad)


def test_merge_overlay_unknown_resource():
    base = {"resources": {"users": {}}}
    overlay = {"resources": {"ghost": {}}}
    with pytest.raises(ValueError, match="unknown resource"):
        merge_accounts_overlay(base, overlay)


def test_merge_overlay_resource_not_mapping():
    base = {"resources": {"users": {}}}
    overlay = {"resources": {"users": "not-a-mapping"}}
    with pytest.raises(ValueError, match="must be a mapping"):
        merge_accounts_overlay(base, overlay)


def test_merge_overlay_merges_accounts_authz_resources():
    base = {
        "authz": {"client_dn_header": "X-Client-Cert-DN"},
        "resources": {"users": {"table": "users", "x": 1}},
    }
    overlay = {
        "accounts": {"CN=x": {"tenant_id": TENANT_A, "grants": {}}},
        "authz": {"session_id_header": "X-Sid"},
        "resources": {"users": {"y": 2}},
    }
    merged = merge_accounts_overlay(base, overlay)
    assert "CN=x" in merged["accounts"]
    assert merged["authz"]["client_dn_header"] == "X-Client-Cert-DN"
    assert merged["authz"]["session_id_header"] == "X-Sid"
    assert merged["resources"]["users"]["x"] == 1
    assert merged["resources"]["users"]["y"] == 2


# ---------------------------------------------------------------- models


def _base_cfg() -> dict:
    return load_config(CONFIG_PATH).model_dump()


def test_account_empty_tenant_rejected():
    base = _base_cfg()
    base["accounts"] = {"CN=x": {"tenant_id": "   ", "grants": {}}}
    with pytest.raises(ValidationError, match="tenant_id"):
        AppConfig.model_validate(base)


def test_account_unknown_operation_rejected():
    base = _base_cfg()
    base["accounts"] = {
        "CN=x": {"tenant_id": TENANT_A, "grants": {"users": {"operations": ["fly"]}}},
    }
    with pytest.raises(ValidationError, match="unknown operation"):
        AppConfig.model_validate(base)


def test_account_unknown_field_rejected():
    base = _base_cfg()
    base["accounts"] = {
        "CN=x": {
            "tenant_id": TENANT_A,
            "grants": {"users": {"fields": {"read": ["nonexistent"]}}},
        },
    }
    with pytest.raises(ValidationError, match="not declared"):
        AppConfig.model_validate(base)


def test_empty_resources_rejected():
    with pytest.raises(ValidationError, match="at least one resource"):
        AppConfig.model_validate({"resources": {}})


# ---------------------------------------------------------------- builder


@pytest.fixture
def users_config():
    return load_config(CONFIG_PATH).resource("users")


@pytest.fixture
def orders_config():
    return load_config(CONFIG_PATH).resource("orders")


def test_coerce_pk_variants():
    assert isinstance(coerce_pk("11111111-1111-1111-1111-111111111111"), UUID)
    assert coerce_pk("123") == 123
    assert coerce_pk("abc-def") == "abc-def"


def test_bad_sort_direction(users_config):
    qb = QueryBuilder("users", users_config)
    ctx = RequestContext(tenant_id=TENANT_A)
    with pytest.raises(Exception) as ei:
        qb.build_select(ctx, sort=[("email", "SIDEWAYS")])
    assert "SORT" in str(ei.value) or getattr(ei.value, "code", "") == "BAD_SORT"


def test_insert_column_denied(users_config):
    qb = QueryBuilder("users", users_config)
    with pytest.raises(Exception) as ei:
        qb.build_insert(["nonexistent"], [{"nonexistent": "x"}])
    assert getattr(ei.value, "code", "") == "COLUMN_DENIED"


def test_insert_empty_payload(users_config):
    qb = QueryBuilder("users", users_config)
    with pytest.raises(Exception) as ei:
        qb.build_insert(["email"], [])
    assert getattr(ei.value, "code", "") == "EMPTY_PAYLOAD"


def test_update_empty_payload(users_config):
    qb = QueryBuilder("users", users_config)
    ctx = RequestContext(tenant_id=TENANT_A)
    with pytest.raises(Exception) as ei:
        qb.build_update(ctx, "some-id", {})
    assert getattr(ei.value, "code", "") == "EMPTY_PAYLOAD"


def test_hard_delete_sql(orders_config):
    qb = QueryBuilder("order_items", orders_config)
    ctx = RequestContext(tenant_id=TENANT_A)
    q = qb.build_hard_delete(ctx, "some-id")
    assert q.sql.startswith("DELETE FROM")


def test_upsert_no_keys(users_config):
    qb = QueryBuilder("users", users_config)
    with pytest.raises(Exception) as ei:
        qb.build_upsert(["email"], [{"email": "a@t.com"}], [], [])
    assert getattr(ei.value, "code", "") == "NO_UPSERT_KEYS"


def test_upsert_do_nothing(users_config):
    qb = QueryBuilder("users", users_config)
    q = qb.build_upsert(
        ["tenant_id", "email"],
        [{"tenant_id": TENANT_A, "email": "a@t.com"}],
        ["tenant_id", "email"],
        [],
    )
    assert "DO NOTHING" in q.sql


def test_related_select_empty(users_config, orders_config):
    qb = QueryBuilder("orders", orders_config)
    ctx = RequestContext(tenant_id=TENANT_A)
    q = qb.build_related_select(
        users_config, foreign_col="user_id", local_values=[], ctx=ctx
    )
    assert "WHERE FALSE" in q.sql


def test_filter_in_empty(users_config):
    qb = QueryBuilder("users", users_config)
    ctx = RequestContext(tenant_id=TENANT_A)
    with pytest.raises(Exception) as ei:
        qb.build_select(ctx, filters={"status": {"in": ""}})
    assert getattr(ei.value, "code", "") == "BAD_FILTER"


# ---------------------------------------------------------------- acl


@pytest.fixture
def cert_dn_config():
    return load_config(CONFIG_PATH, accounts_path=ACCOUNTS_PATH)


def test_acl_operation_disabled(cert_dn_config):
    rc = cert_dn_config.resource("users").model_copy(deep=True)
    rc.operations.create = False
    grant = RoleAccess(operations=["create"])
    acl = ACLChecker("users", rc, account_grant=grant)
    ctx = RequestContext(account_dn=ORDERS_READER_DN, trusted=True)
    with pytest.raises(ForbiddenError) as ei:
        acl.require_operation(ctx, "create")
    assert ei.value.code == "OPERATION_DISABLED"


def test_acl_grant_no_fields_returns_base(cert_dn_config):
    grant = RoleAccess(operations=["list"], fields=None)
    acl = ACLChecker("users", cert_dn_config.resource("users"), account_grant=grant)
    ctx = RequestContext(account_dn=ORDERS_READER_DN, trusted=True)
    assert "email" in acl.readable_fields(ctx)
    assert "id" in acl.readable_fields(ctx)
    assert "email" in acl.writable_fields(ctx)


# ---------------------------------------------------------------- authz


@pytest.mark.asyncio
async def test_authz_unknown_resource(cert_dn_config):
    authz = CertDnAuthz(cert_dn_config)
    ctx = RequestContext(account_dn=ORDERS_READER_DN, trusted=True)
    assert await authz.allow(ctx, "ghost", "list") is False


@pytest.mark.asyncio
async def test_authz_unknown_account(cert_dn_config):
    authz = CertDnAuthz(cert_dn_config)
    ctx = RequestContext(account_dn="CN=ghost,O=Acme,C=RU", trusted=True)
    assert await authz.allow(ctx, "orders", "list") is False


# ---------------------------------------------------------------- service


def test_service_unknown_resource(cert_dn_config):
    service = ResourceService(cert_dn_config, None, CertDnAuthz(cert_dn_config))
    with pytest.raises(NotFoundError):
        service._resource("ghost")


def test_service_inject_missing_tenant(cert_dn_config):
    service = ResourceService(cert_dn_config, None, CertDnAuthz(cert_dn_config))
    ctx = RequestContext(tenant_id=None)
    with pytest.raises(ForbiddenError) as ei:
        service._inject_row_context(ctx, cert_dn_config.resource("users"), {})
    assert ei.value.code == "MISSING_TENANT"


# ---------------------------------------------------------------- db


def test_db_require_pool_uninitialized():
    db = Database("postgresql://x")
    with pytest.raises(RuntimeError, match="pool"):
        db.require_pool()


# ---------------------------------------------------------------- context / errors / middleware


def test_get_request_context_default():
    clear_request_context()
    ctx = get_request_context()
    assert ctx.tenant_id is None
    assert ctx.account_dn is None
    assert ctx.trusted is False


def test_error_body():
    assert error_body("x", "Y") == {"detail": "x", "code": "Y"}


@pytest.mark.asyncio
async def test_middleware_non_http_passthrough():
    class App:
        def __init__(self) -> None:
            self.called = False

        async def __call__(self, scope, receive, send) -> None:
            self.called = True

    app = App()
    from pg_gateway.config.models import AuthzConfig

    mw = RequestContextMiddleware(app, AuthzConfig(), account_tenants={})
    await mw({"type": "websocket"}, _receive, _send)
    assert app.called is True


async def _receive():
    return {"type": "http.request", "body": b"", "more_body": False}


async def _send(message):
    pass


# ---------------------------------------------------------------- settings


def test_settings_from_env_defaults(monkeypatch):
    env_keys = (
        "DATABASE_URL",
        "CONFIG_PATH",
        "ACCOUNTS_CONFIG_PATH",
        "HOST",
        "PORT",
        "LOG_LEVEL",
        "RELOAD_INTERVAL",
    )
    for k in env_keys:
        monkeypatch.delenv(k, raising=False)
    s = Settings.from_env()
    assert s.database_url == "postgresql://gateway:gateway@localhost:5432/gateway"
    assert s.reload_interval == 2.0
