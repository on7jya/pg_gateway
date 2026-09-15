from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

from tests.conftest import TENANT_A, USER_ALICE

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_ready(client: AsyncClient):
    r = await client.get("/ready")
    assert r.status_code == 200
    assert r.json()["status"] == "ready"


@pytest.mark.asyncio
async def test_list_users(client: AsyncClient, admin_headers: dict):
    r = await client.get("/api/v1/users", headers=admin_headers)
    assert r.status_code == 200
    body = r.json()
    assert "data" in body and "meta" in body
    assert body["meta"]["total"] >= 2
    emails = {u["email"] for u in body["data"]}
    assert "alice@acme.test" in emails
    # tenant isolation: no carol
    assert "carol@other.test" not in emails


@pytest.mark.asyncio
async def test_missing_tenant_403(client: AsyncClient):
    r = await client.get("/api/v1/users", headers={"X-Roles": "admin"})
    assert r.status_code == 403
    body = r.json()
    assert "detail" in body and "code" in body
    assert body["code"] == "MISSING_TENANT"


@pytest.mark.asyncio
async def test_reader_cannot_create(client: AsyncClient, reader_headers: dict):
    r = await client.post(
        "/api/v1/users",
        headers=reader_headers,
        json={"email": "nope@acme.test", "full_name": "Nope"},
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_get_user_with_orders(client: AsyncClient, admin_headers: dict):
    r = await client.get(
        f"/api/v1/users/{USER_ALICE}?include=orders",
        headers=admin_headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["email"] == "alice@acme.test"
    assert isinstance(body.get("orders"), list)
    assert len(body["orders"]) >= 1


@pytest.mark.asyncio
async def test_filter_users(client: AsyncClient, admin_headers: dict):
    r = await client.get(
        "/api/v1/users?filter[email][eq]=bob@acme.test",
        headers=admin_headers,
    )
    assert r.status_code == 200
    data = r.json()["data"]
    assert len(data) == 1
    assert data[0]["full_name"] == "Bob Buyer"


@pytest.mark.asyncio
async def test_crud_soft_delete_cycle(client: AsyncClient, admin_headers: dict):
    email = f"tmp-{uuid.uuid4().hex[:8]}@acme.test"
    # create
    r = await client.post(
        "/api/v1/users",
        headers=admin_headers,
        json={"email": email, "full_name": "Temp User", "status": "active"},
    )
    assert r.status_code == 201, r.text
    user = r.json()
    uid = user["id"]

    # patch
    r = await client.patch(
        f"/api/v1/users/{uid}",
        headers=admin_headers,
        json={"full_name": "Temp Updated"},
    )
    assert r.status_code == 200
    assert r.json()["full_name"] == "Temp Updated"

    # put
    r = await client.put(
        f"/api/v1/users/{uid}",
        headers=admin_headers,
        json={"email": email, "full_name": "Temp Put", "status": "active"},
    )
    assert r.status_code == 200
    assert r.json()["full_name"] == "Temp Put"

    # soft delete
    r = await client.delete(f"/api/v1/users/{uid}", headers=admin_headers)
    assert r.status_code == 200
    assert r.json().get("deleted_at") is not None

    # hidden by default
    r = await client.get(f"/api/v1/users/{uid}", headers=admin_headers)
    assert r.status_code == 404

    # visible with include_deleted
    r = await client.get(
        f"/api/v1/users/{uid}?include_deleted=true",
        headers=admin_headers,
    )
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_not_found(client: AsyncClient, admin_headers: dict):
    r = await client.get(
        f"/api/v1/users/{uuid.uuid4()}",
        headers=admin_headers,
    )
    assert r.status_code == 404
    assert r.json()["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_unique_violation_409(client: AsyncClient, admin_headers: dict):
    r = await client.post(
        "/api/v1/users",
        headers=admin_headers,
        json={"email": "alice@acme.test", "full_name": "Dup"},
    )
    assert r.status_code == 409
    assert r.json()["code"] == "UNIQUE_VIOLATION"


@pytest.mark.asyncio
async def test_validation_400(client: AsyncClient, admin_headers: dict):
    r = await client.post(
        "/api/v1/users",
        headers=admin_headers,
        json={"full_name": "Missing Email"},
    )
    assert r.status_code == 400
    assert "detail" in r.json() and "code" in r.json()


@pytest.mark.asyncio
async def test_batch_and_upsert(client: AsyncClient, admin_headers: dict):
    e1 = f"batch1-{uuid.uuid4().hex[:6]}@acme.test"
    e2 = f"batch2-{uuid.uuid4().hex[:6]}@acme.test"
    r = await client.post(
        "/api/v1/users/batch",
        headers=admin_headers,
        json={
            "items": [
                {"email": e1, "full_name": "B1", "status": "active"},
                {"email": e2, "full_name": "B2", "status": "active"},
            ]
        },
    )
    assert r.status_code == 201, r.text
    assert len(r.json()) == 2

    r = await client.post(
        "/api/v1/users/upsert",
        headers=admin_headers,
        json={"items": [{"email": e1, "full_name": "B1 Upserted", "status": "active"}]},
    )
    assert r.status_code == 200, r.text
    assert r.json()[0]["full_name"] == "B1 Upserted"


@pytest.mark.asyncio
async def test_aggregate_orders(client: AsyncClient, admin_headers: dict):
    r = await client.post(
        "/api/v1/orders/aggregate",
        headers=admin_headers,
        json={"function": "sum", "field": "total_amount", "group_by": ["status"]},
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert isinstance(data, list)
    assert len(data) >= 1


@pytest.mark.asyncio
async def test_bulk_delete(client: AsyncClient, admin_headers: dict):
    email = f"bulk-{uuid.uuid4().hex[:8]}@acme.test"
    r = await client.post(
        "/api/v1/users",
        headers=admin_headers,
        json={"email": email, "full_name": "Bulk Me", "status": "inactive"},
    )
    assert r.status_code == 201
    uid = r.json()["id"]

    r = await client.post(
        "/api/v1/users/bulk-delete",
        headers=admin_headers,
        json={"ids": [uid]},
    )
    assert r.status_code == 200
    assert r.json()["deleted"] == 1

    r = await client.get(f"/api/v1/users/{uid}", headers=admin_headers)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_tenant_b_isolation(client: AsyncClient, tenant_b_headers: dict):
    r = await client.get("/api/v1/users", headers=tenant_b_headers)
    assert r.status_code == 200
    emails = {u["email"] for u in r.json()["data"]}
    assert "carol@other.test" in emails
    assert "alice@acme.test" not in emails


@pytest.mark.asyncio
async def test_orders_list_and_items_include(client: AsyncClient, admin_headers: dict):
    r = await client.get("/api/v1/orders?include=items", headers=admin_headers)
    assert r.status_code == 200
    data = r.json()["data"]
    assert len(data) >= 1
    assert "items" in data[0]
