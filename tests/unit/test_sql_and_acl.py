from __future__ import annotations

import pytest

from pg_gateway.acl import ACLChecker
from pg_gateway.config import load_config
from pg_gateway.context import RequestContext
from pg_gateway.errors import ForbiddenError, ValidationAppError
from pg_gateway.main import _known_roles
from pg_gateway.service import parse_filter_query_params
from pg_gateway.sql.builder import QueryBuilder, parse_sort_param, quote_ident
from tests.conftest import CONFIG_PATH, TENANT_A


@pytest.fixture
def users_config():
    return load_config(CONFIG_PATH).resource("users")


@pytest.fixture
def orders_config():
    return load_config(CONFIG_PATH).resource("orders")


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
    assert parse_sort_param("+status") == [("status", "ASC")]
    assert parse_sort_param(None) == []
    assert parse_sort_param("") == []


def test_build_select_applies_tenant_and_soft_delete(users_config):
    qb = QueryBuilder("users", users_config)
    ctx = RequestContext(tenant_id=TENANT_A, roles=("admin",))
    q = qb.build_select(ctx, limit=10, offset=0)
    assert "tenant_id" in q.sql
    assert "deleted_at" in q.sql
    assert "IS NULL" in q.sql
    assert q.args[0] == TENANT_A
    assert 10 in q.args


def test_build_select_include_deleted_omits_soft_delete_clause(users_config):
    qb = QueryBuilder("users", users_config)
    ctx = RequestContext(tenant_id=TENANT_A, roles=("admin",))
    q = qb.build_select(ctx, include_deleted=True)
    assert "deleted_at IS NULL" not in q.sql


def test_missing_tenant_raises(users_config):
    qb = QueryBuilder("users", users_config)
    ctx = RequestContext(tenant_id=None, roles=("admin",))
    with pytest.raises(ForbiddenError) as ei:
        qb.build_select(ctx)
    assert ei.value.code == "MISSING_TENANT"


def test_filter_ops_eq_ilike(users_config):
    qb = QueryBuilder("users", users_config)
    ctx = RequestContext(tenant_id=TENANT_A, roles=("admin",))
    q = qb.build_select(
        ctx,
        filters={"status": {"eq": "active"}, "email": {"ilike": "%acme%"}},
    )
    assert "ILIKE" in q.sql
    assert "active" in q.args


def test_filter_ops_comparison_in_like_is_null(orders_config):
    qb = QueryBuilder("orders", orders_config)
    ctx = RequestContext(tenant_id=TENANT_A, roles=("admin",))
    q = qb.build_select(
        ctx,
        filters={
            "total_amount": {"gte": "40", "lt": "200"},
            "status": {"in": "paid,pending", "ne": "cancelled"},
            "order_number": {"like": "ORD-%"},
        },
    )
    assert ">=" in q.sql and "<" in q.sql
    assert "IN (" in q.sql
    assert "<>" in q.sql
    assert "LIKE" in q.sql
    assert "paid" in q.args and "pending" in q.args

    q_null = qb.build_select(ctx, filters={"status": {"is_null": "false"}})
    assert "IS NOT NULL" in q_null.sql

    q_is = qb.build_select(ctx, filters={"status": {"is_null": "true"}})
    assert "IS NULL" in q_is.sql


def test_filter_denied_and_bad_op(users_config):
    qb = QueryBuilder("users", users_config)
    ctx = RequestContext(tenant_id=TENANT_A, roles=("admin",))
    with pytest.raises(ValidationAppError) as ei:
        qb.build_select(ctx, filters={"tenant_id": {"eq": TENANT_A}})
    assert ei.value.code == "FILTER_DENIED"
    with pytest.raises(ValidationAppError) as ei2:
        qb.build_select(ctx, filters={"status": {"regex": "x"}})
    assert ei2.value.code == "BAD_FILTER_OP"


def test_sort_denied(users_config):
    qb = QueryBuilder("users", users_config)
    ctx = RequestContext(tenant_id=TENANT_A, roles=("admin",))
    with pytest.raises(ValidationAppError) as ei:
        qb.build_select(ctx, sort=[("tenant_id", "ASC")])
    assert ei.value.code == "SORT_DENIED"


def test_parse_filter_query_params():
    class QP:
        def multi_items(self):
            return [
                ("filter[status][eq]", "active"),
                ("filter[email][ilike]", "%a%"),
                ("limit", "10"),
            ]

    filters = parse_filter_query_params(QP())
    assert filters == {"status": {"eq": "active"}, "email": {"ilike": "%a%"}}


def test_parse_filter_query_params_bad_key():
    class QP:
        def multi_items(self):
            return [("filter[status]", "active")]

    with pytest.raises(ValidationAppError) as ei:
        parse_filter_query_params(QP())
    assert ei.value.code == "BAD_FILTER"


def test_acl_reader_cannot_create(users_config):
    acl = ACLChecker("users", users_config)
    ctx = RequestContext(tenant_id=TENANT_A, roles=("reader",))
    with pytest.raises(ForbiddenError):
        acl.require_operation(ctx, "create")


def test_acl_admin_can_create(users_config):
    acl = ACLChecker("users", users_config)
    ctx = RequestContext(tenant_id=TENANT_A, roles=("admin",))
    acl.require_operation(ctx, "create")


def test_acl_reader_cannot_mutate(users_config):
    acl = ACLChecker("users", users_config)
    ctx = RequestContext(tenant_id=TENANT_A, roles=("reader",))
    for op in ("update", "patch", "delete", "bulk_delete", "upsert", "batch_create"):
        with pytest.raises(ForbiddenError) as ei:
            acl.require_operation(ctx, op)
        assert ei.value.code == "OPERATION_DENIED"


def test_acl_readable_fields_reader(users_config):
    acl = ACLChecker("users", users_config)
    ctx = RequestContext(tenant_id=TENANT_A, roles=("reader",), trusted=True)
    fields = acl.readable_fields(ctx)
    assert "email" in fields
    assert "deleted_at" not in fields


def test_acl_writable_fields_exclude_deleted_at(users_config):
    acl = ACLChecker("users", users_config)
    admin = RequestContext(tenant_id=TENANT_A, roles=("admin",), trusted=True)
    reader = RequestContext(tenant_id=TENANT_A, roles=("reader",), trusted=True)
    assert "deleted_at" not in acl.writable_fields(admin)
    assert "tenant_id" not in acl.writable_fields(admin)
    assert acl.writable_fields(reader) == set()
    assert "deleted_at" not in acl.filter_read_payload(
        reader, {"email": "a", "deleted_at": "x"}
    )


@pytest.mark.asyncio
async def test_header_stub_authz_requires_trusted_role(app_config):
    from pg_gateway.authz import HeaderStubAuthz

    authz = HeaderStubAuthz(app_config)
    denied = RequestContext(tenant_id=TENANT_A, roles=("admin",), trusted=False)
    assert await authz.allow(denied, "users", "list") is False
    no_roles = RequestContext(tenant_id=TENANT_A, roles=(), trusted=True)
    assert await authz.allow(no_roles, "users", "list") is False
    unknown = RequestContext(tenant_id=TENANT_A, roles=("ghost",), trusted=True)
    assert await authz.allow(unknown, "users", "list") is False
    ok = RequestContext(tenant_id=TENANT_A, roles=("admin",), trusted=True)
    assert await authz.allow(ok, "users", "list") is True


def test_aggregate_whitelist(users_config):
    qb = QueryBuilder("users", users_config)
    ctx = RequestContext(tenant_id=TENANT_A, roles=("admin",))
    q = qb.build_aggregate(ctx, function="count", group_by=["status"])
    assert "COUNT(*)" in q.sql
    assert "GROUP BY" in q.sql
    with pytest.raises(ValidationAppError):
        qb.build_aggregate(ctx, function="avg")


def test_aggregate_sum_and_group_denied(orders_config):
    qb = QueryBuilder("orders", orders_config)
    ctx = RequestContext(tenant_id=TENANT_A, roles=("admin",))
    q = qb.build_aggregate(
        ctx, function="sum", field="total_amount", group_by=["status"]
    )
    assert "SUM(" in q.sql
    with pytest.raises(ValidationAppError) as ei:
        qb.build_aggregate(ctx, function="sum", field="order_number")
    assert ei.value.code == "SUM_DENIED"
    with pytest.raises(ValidationAppError) as ei2:
        qb.build_aggregate(ctx, function="count", group_by=["order_number"])
    assert ei2.value.code == "GROUP_DENIED"


def test_bulk_delete_requires_ids_or_filters(users_config):
    qb = QueryBuilder("users", users_config)
    ctx = RequestContext(tenant_id=TENANT_A, roles=("admin",))
    with pytest.raises(ValidationAppError) as ei:
        qb.build_bulk_delete(ctx)
    assert ei.value.code == "EMPTY_BULK_DELETE"


def test_bulk_delete_soft_sql(users_config):
    qb = QueryBuilder("users", users_config)
    ctx = RequestContext(tenant_id=TENANT_A, roles=("admin",))
    q = qb.build_bulk_delete(
        ctx, filters={"status": {"eq": "inactive"}}, soft=True
    )
    assert q.sql.startswith("UPDATE")
    assert "deleted_at" in q.sql
    assert "inactive" in q.args


def test_upsert_sql_conflict(users_config):
    qb = QueryBuilder("users", users_config)
    rows = [{"tenant_id": TENANT_A, "email": "a@t.com", "full_name": "A", "status": "active"}]
    q = qb.build_upsert(
        ["tenant_id", "email", "full_name", "status"],
        rows,
        ["tenant_id", "email"],
        ["full_name", "status"],
    )
    assert "ON CONFLICT" in q.sql
    assert "DO UPDATE SET" in q.sql


def test_config_loads_demo():
    cfg = load_config(CONFIG_PATH)
    assert set(cfg.resources) == {"users", "orders", "order_items"}
    assert cfg.gateway.pagination.default_limit == 20
    assert cfg.authz.trust_header == "X-Gateway-Token"
    known = _known_roles(cfg)
    assert known == frozenset({"admin", "reader"})


def test_config_rejects_invalid_root(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("- not a mapping\n", encoding="utf-8")
    with pytest.raises(ValueError, match="mapping"):
        from pg_gateway.config.loader import load_yaml

        load_yaml(bad)
