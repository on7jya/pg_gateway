"""Second batch of edge tests: models validation, service/builder edges, schema."""

from __future__ import annotations

import asyncpg
import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from pg_gateway.acl import ACLChecker
from pg_gateway.authz import CertDnAuthz
from pg_gateway.config import Settings, load_config
from pg_gateway.config.models import (
    AppConfig,
    FieldConfig,
    FieldType,
    ResourceConfig,
    RoleAccess,
    RoleFieldAccess,
    RowFilterConfig,
)
from pg_gateway.context import (
    RequestContext,
    clear_request_context,
    set_request_context,
)
from pg_gateway.errors import TimeoutAppError
from pg_gateway.main import create_app
from pg_gateway.schemas import create_response_model
from pg_gateway.service import ResourceService
from pg_gateway.sql.builder import QueryBuilder
from tests.conftest import ACCOUNTS_PATH, CONFIG_PATH, ORDERS_READER_DN, TENANT_A

ADMIN_DN = "CN=admin,OU=tuz,O=Acme,C=RU"


@pytest.fixture
def cert_dn_config():
    return load_config(CONFIG_PATH, accounts_path=ACCOUNTS_PATH)


def _base_cfg() -> dict:
    return load_config(CONFIG_PATH).model_dump()


# ---------------------------------------------------------------- models


def test_resource_pk_not_declared_rejected():
    with pytest.raises(ValidationError, match="pk"):
        ResourceConfig(
            table="t",
            pk="id",
            fields={"email": FieldConfig(type=FieldType.STRING)},
        )


def test_account_empty_dn_key_rejected():
    base = _base_cfg()
    base["accounts"] = {"": {"tenant_id": TENANT_A, "grants": {}}}
    with pytest.raises(ValidationError, match="non-empty"):
        AppConfig.model_validate(base)


def test_account_disabled_operation_rejected():
    base = _base_cfg()
    base["resources"]["users"]["operations"]["create"] = False
    base["accounts"] = {
        "CN=x": {"tenant_id": TENANT_A, "grants": {"users": {"operations": ["create"]}}},
    }
    with pytest.raises(ValidationError, match="disabled"):
        AppConfig.model_validate(base)


def test_account_grant_fields_none_sides():
    base = _base_cfg()
    base["accounts"] = {
        "CN=x": {
            "tenant_id": TENANT_A,
            "grants": {"users": {"fields": {"read": None, "write": None}}},
        },
    }
    cfg = AppConfig.model_validate(base)
    assert "CN=x" in cfg.accounts


def test_normalize_account_dns_non_dict():
    base = _base_cfg()
    base["accounts"] = "not-a-dict"
    with pytest.raises(ValidationError):
        AppConfig.model_validate(base)


# ---------------------------------------------------------------- acl


def test_acl_grant_fields_read_write_none(cert_dn_config):
    grant = RoleAccess(
        operations=["list"],
        fields=RoleFieldAccess(read=None, write=None),
    )
    acl = ACLChecker("users", cert_dn_config.resource("users"), account_grant=grant)
    ctx = RequestContext(account_dn=ORDERS_READER_DN, trusted=True)
    assert "email" in acl.readable_fields(ctx)
    assert "email" in acl.writable_fields(ctx)


# ---------------------------------------------------------------- errors


def test_timeout_app_error_default():
    e = TimeoutAppError()
    assert e.code == "TIMEOUT"
    assert e.status_code == 504


# ---------------------------------------------------------------- schemas


def test_schema_json_and_read_false():
    cfg = ResourceConfig(
        table="t",
        pk="id",
        fields={
            "id": FieldConfig(type=FieldType.UUID, read=True, primary_key=True),
            "meta": FieldConfig(type=FieldType.JSON, read=True),
            "secret": FieldConfig(type=FieldType.STRING, read=False, write=True),
        },
    )
    model = create_response_model("t", cfg)
    assert "meta" in model.model_fields
    assert "secret" not in model.model_fields


# ---------------------------------------------------------------- builder


def test_apply_row_filters_optional_missing():
    cfg = ResourceConfig(
        table="t",
        pk="id",
        fields={"id": FieldConfig(type=FieldType.UUID, primary_key=True)},
        row_filters=[
            RowFilterConfig(column="tenant_id", from_context="tenant_id", required=False)
        ],
    )
    qb = QueryBuilder("t", cfg)
    ctx = RequestContext(tenant_id=None)
    q = qb.build_select(ctx)
    assert "tenant_id" not in q.sql


def test_filter_in_bad_value():
    cfg = load_config(CONFIG_PATH).resource("users")
    qb = QueryBuilder("users", cfg)
    ctx = RequestContext(tenant_id=TENANT_A)
    with pytest.raises(Exception) as ei:
        qb.build_select(ctx, filters={"status": {"in": 123}})
    assert getattr(ei.value, "code", "") == "BAD_FILTER"


# ---------------------------------------------------------------- service


class _CancelDb:
    async def fetchrow(self, sql, *args):
        raise asyncpg.exceptions.QueryCanceledError("canceled")

    async def fetch(self, sql, *args):
        raise asyncpg.exceptions.QueryCanceledError("canceled")

    async def fetchval(self, sql, *args):
        raise asyncpg.exceptions.QueryCanceledError("canceled")


class _TimeoutDb:
    async def fetchrow(self, sql, *args):
        raise TimeoutError()


@pytest.mark.asyncio
async def test_service_run_query_canceled(cert_dn_config):
    service = ResourceService(cert_dn_config, _CancelDb(), CertDnAuthz(cert_dn_config))
    with pytest.raises(TimeoutAppError):
        await service._run("SELECT 1", [])


@pytest.mark.asyncio
async def test_service_run_timeout(cert_dn_config):
    service = ResourceService(cert_dn_config, _TimeoutDb(), CertDnAuthz(cert_dn_config))
    with pytest.raises(TimeoutAppError):
        await service._run("SELECT 1", [], one=True)


@pytest.mark.asyncio
async def test_service_create_field_denied(cert_dn_config):
    service = ResourceService(cert_dn_config, None, CertDnAuthz(cert_dn_config))
    ctx = RequestContext(account_dn=ADMIN_DN, tenant_id=TENANT_A, trusted=True)
    set_request_context(ctx)
    try:
        with pytest.raises(Exception) as ei:
            await service.create(
                "users",
                {"email": "x@t.com", "full_name": "X", "deleted_at": "2020-01-01T00:00:00Z"},
            )
        assert getattr(ei.value, "code", "") == "FIELD_DENIED"
    finally:
        clear_request_context()


@pytest.mark.asyncio
async def test_service_batch_empty(cert_dn_config):
    service = ResourceService(cert_dn_config, None, CertDnAuthz(cert_dn_config))
    ctx = RequestContext(account_dn=ADMIN_DN, tenant_id=TENANT_A, trusted=True)
    set_request_context(ctx)
    try:
        with pytest.raises(Exception) as ei:
            await service.batch_create("users", [])
        assert getattr(ei.value, "code", "") == "EMPTY_PAYLOAD"
    finally:
        clear_request_context()


# ---------------------------------------------------------------- main


@pytest.mark.asyncio
async def test_ready_db_not_connected_503(cert_dn_config):
    settings = Settings(
        config_path=str(CONFIG_PATH),
        database_url="postgresql://x",
        accounts_config_path=str(ACCOUNTS_PATH),
    )
    app = create_app(config=cert_dn_config, settings=settings, connect_db=False)
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get("/ready", headers={"X-Client-Cert-DN": ORDERS_READER_DN})
            assert r.status_code == 503
            assert r.json()["code"] == "NOT_READY"


# ---------------------------------------------------------------- acl (grant None)


def test_acl_no_grant_empty_fields(cert_dn_config):
    acl = ACLChecker("users", cert_dn_config.resource("users"), account_grant=None)
    ctx = RequestContext(account_dn=ORDERS_READER_DN, trusted=True)
    assert acl.readable_fields(ctx) == set()
    assert acl.writable_fields(ctx) == set()


# ---------------------------------------------------------------- builder (parse sort)


def test_parse_sort_param_empty_parts():
    from pg_gateway.sql.builder import parse_sort_param

    assert parse_sort_param("email,,status") == [("email", "ASC"), ("status", "ASC")]
    assert parse_sort_param(",email") == [("email", "ASC")]


# ---------------------------------------------------------------- service (primary key)


class _RowDb:
    async def fetch(self, sql, *args):
        return [
            {
                "id": "a0000000-0000-0000-0000-000000000001",
                "tenant_id": TENANT_A,
                "email": "x@t.com",
                "full_name": "X",
                "status": "active",
                "created_at": None,
                "deleted_at": None,
            }
        ]


@pytest.mark.asyncio
async def test_service_create_primary_key_ignored(cert_dn_config):
    service = ResourceService(cert_dn_config, _RowDb(), CertDnAuthz(cert_dn_config))
    ctx = RequestContext(account_dn=ADMIN_DN, tenant_id=TENANT_A, trusted=True)
    set_request_context(ctx)
    try:
        result = await service.create(
            "users",
            {"id": "a0000000-0000-0000-0000-000000000009", "email": "x@t.com", "full_name": "X"},
        )
        assert result["email"] == "x@t.com"
    finally:
        clear_request_context()


@pytest.mark.asyncio
async def test_service_batch_heterogeneous_rejected(cert_dn_config):
    service = ResourceService(cert_dn_config, None, CertDnAuthz(cert_dn_config))
    ctx = RequestContext(account_dn=ADMIN_DN, tenant_id=TENANT_A, trusted=True)
    set_request_context(ctx)
    try:
        with pytest.raises(Exception) as ei:
            await service.batch_create(
                "users",
                [
                    {"email": "a@t.com", "full_name": "A"},
                    {"email": "b@t.com", "full_name": "B", "status": "active"},
                ],
            )
        assert getattr(ei.value, "code", "") == "BATCH_SHAPE_MISMATCH"
    finally:
        clear_request_context()


@pytest.mark.asyncio
async def test_service_upsert_heterogeneous_rejected(cert_dn_config):
    service = ResourceService(cert_dn_config, None, CertDnAuthz(cert_dn_config))
    ctx = RequestContext(account_dn=ADMIN_DN, tenant_id=TENANT_A, trusted=True)
    set_request_context(ctx)
    try:
        with pytest.raises(Exception) as ei:
            await service.upsert(
                "users",
                [
                    {"email": "a@t.com", "full_name": "A"},
                    {"email": "b@t.com", "full_name": "B", "status": "active"},
                ],
            )
        assert getattr(ei.value, "code", "") == "UPSERT_SHAPE_MISMATCH"
    finally:
        clear_request_context()
