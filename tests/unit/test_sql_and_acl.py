from __future__ import annotations

import pytest

from pg_gateway.acl import ACLChecker
from pg_gateway.config import load_config
from pg_gateway.context import RequestContext
from pg_gateway.errors import ForbiddenError, ValidationAppError
from pg_gateway.sql.builder import QueryBuilder, parse_sort_param, quote_ident
from tests.conftest import CONFIG_PATH, TENANT_A


@pytest.fixture
def users_config():
    return load_config(CONFIG_PATH).resource("users")


def test_quote_ident_allows_valid():
    assert quote_ident("users", allowed={"users"}) == '"users"'


def test_quote_ident_rejects_injection():
    with pytest.raises(ValidationAppError):
        quote_ident('users"; drop table users;--', allowed={"users"})


def test_quote_ident_rejects_non_whitelist():
    with pytest.raises(ValidationAppError):
        quote_ident("secret", allowed={"users"})


def test_parse_sort_param():
    assert parse_sort_param("-created_at,email") == [
        ("created_at", "DESC"),
        ("email", "ASC"),
    ]


def test_build_select_applies_tenant_and_soft_delete(users_config):
    qb = QueryBuilder("users", users_config)
    ctx = RequestContext(tenant_id=TENANT_A, roles=("admin",))
    q = qb.build_select(ctx, limit=10, offset=0)
    assert "tenant_id" in q.sql
    assert "deleted_at" in q.sql
    assert q.args[0] == TENANT_A
    assert 10 in q.args


def test_missing_tenant_raises(users_config):
    qb = QueryBuilder("users", users_config)
    ctx = RequestContext(tenant_id=None, roles=("admin",))
    with pytest.raises(ForbiddenError) as ei:
        qb.build_select(ctx)
    assert ei.value.code == "MISSING_TENANT"


def test_filter_ops(users_config):
    qb = QueryBuilder("users", users_config)
    ctx = RequestContext(tenant_id=TENANT_A, roles=("admin",))
    q = qb.build_select(
        ctx,
        filters={"status": {"eq": "active"}, "email": {"ilike": "%acme%"}},
    )
    assert "ILIKE" in q.sql
    assert "active" in q.args


def test_acl_reader_cannot_create(users_config):
    acl = ACLChecker("users", users_config)
    ctx = RequestContext(tenant_id=TENANT_A, roles=("reader",))
    with pytest.raises(ForbiddenError):
        acl.require_operation(ctx, "create")


def test_acl_admin_can_create(users_config):
    acl = ACLChecker("users", users_config)
    ctx = RequestContext(tenant_id=TENANT_A, roles=("admin",))
    acl.require_operation(ctx, "create")


def test_acl_readable_fields_reader(users_config):
    acl = ACLChecker("users", users_config)
    ctx = RequestContext(tenant_id=TENANT_A, roles=("reader",))
    fields = acl.readable_fields(ctx)
    assert "email" in fields
    assert "deleted_at" not in fields


def test_aggregate_whitelist(users_config):
    qb = QueryBuilder("users", users_config)
    ctx = RequestContext(tenant_id=TENANT_A, roles=("admin",))
    q = qb.build_aggregate(ctx, function="count", group_by=["status"])
    assert "COUNT(*)" in q.sql
    assert "GROUP BY" in q.sql
    with pytest.raises(ValidationAppError):
        qb.build_aggregate(ctx, function="avg")


def test_config_loads_demo():
    cfg = load_config(CONFIG_PATH)
    assert set(cfg.resources) == {"users", "orders", "order_items"}
    assert cfg.gateway.pagination.default_limit == 20
