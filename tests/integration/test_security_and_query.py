from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

from tests.conftest import (
    ORDER_ALICE,
    ORDER_CAROL,
    TENANT_A,
    TENANT_B,
    USER_ALICE,
    USER_CAROL,
    gateway_headers,
)

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_wrong_trust_token_401(client: AsyncClient):
    r = await client.get(
        "/api/v1/users",
        headers=gateway_headers(token="nope"),
    )
    assert r.status_code == 401
    assert r.json()["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_health_open_no_auth(client: AsyncClient):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_reader_cannot_update_or_delete(client: AsyncClient, reader_headers: dict):
    r = await client.patch(
        f"/api/v1/users/{USER_ALICE}",
        headers=reader_headers,
        json={"full_name": "Hacked"},
    )
    assert r.status_code == 403

    r = await client.put(
        f"/api/v1/users/{USER_ALICE}",
        headers=reader_headers,
        json={"email": "alice@acme.test", "full_name": "Hacked", "status": "active"},
    )
    assert r.status_code == 403

    r = await client.delete(f"/api/v1/users/{USER_ALICE}", headers=reader_headers)
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_reader_field_acl_hides_deleted_at(
    client: AsyncClient, admin_headers: dict, reader_headers: dict
):
    email = f"acl-{uuid.uuid4().hex[:8]}@acme.test"
    r = await client.post(
        "/api/v1/users",
        headers=admin_headers,
        json={"email": email, "full_name": "ACL Soft", "status": "active"},
    )
    assert r.status_code == 201
    uid = r.json()["id"]

    r = await client.delete(f"/api/v1/users/{uid}", headers=admin_headers)
    assert r.status_code == 200
    assert r.json().get("deleted_at") is not None

    r = await client.get(
        f"/api/v1/users/{uid}?include_deleted=true",
        headers=reader_headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert "deleted_at" not in body
    assert body["email"] == email


@pytest.mark.asyncio
async def test_admin_sees_deleted_at_with_include_deleted(
    client: AsyncClient, admin_headers: dict
):
    email = f"delvis-{uuid.uuid4().hex[:8]}@acme.test"
    r = await client.post(
        "/api/v1/users",
        headers=admin_headers,
        json={"email": email, "full_name": "Del Vis", "status": "active"},
    )
    uid = r.json()["id"]
    await client.delete(f"/api/v1/users/{uid}", headers=admin_headers)

    r = await client.get(
        f"/api/v1/users/{uid}?include_deleted=true",
        headers=admin_headers,
    )
    assert r.status_code == 200
    assert r.json().get("deleted_at") is not None


@pytest.mark.asyncio
async def test_include_deleted_list_admin_vs_reader(
    client: AsyncClient, admin_headers: dict, reader_headers: dict
):
    email = f"listdel-{uuid.uuid4().hex[:8]}@acme.test"
    r = await client.post(
        "/api/v1/users",
        headers=admin_headers,
        json={"email": email, "full_name": "List Del", "status": "active"},
    )
    uid = r.json()["id"]
    await client.delete(f"/api/v1/users/{uid}", headers=admin_headers)

    r = await client.get("/api/v1/users", headers=admin_headers)
    assert uid not in {u["id"] for u in r.json()["data"]}

    r = await client.get("/api/v1/users?include_deleted=true", headers=admin_headers)
    assert uid in {u["id"] for u in r.json()["data"]}

    # Current behavior: readers may also use include_deleted (no role gate on the flag).
    r = await client.get("/api/v1/users?include_deleted=true", headers=reader_headers)
    assert r.status_code == 200
    match = next(u for u in r.json()["data"] if u["id"] == uid)
    assert "deleted_at" not in match


@pytest.mark.asyncio
async def test_tenant_a_cannot_get_tenant_b_user(
    client: AsyncClient, admin_headers: dict
):
    r = await client.get(f"/api/v1/users/{USER_CAROL}", headers=admin_headers)
    assert r.status_code == 404
    assert r.json()["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_tenant_a_cannot_get_tenant_b_order(
    client: AsyncClient, admin_headers: dict
):
    r = await client.get(f"/api/v1/orders/{ORDER_CAROL}", headers=admin_headers)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_create_stamps_tenant_from_context(
    client: AsyncClient, admin_headers: dict
):
    email = f"stamp-{uuid.uuid4().hex[:8]}@acme.test"
    r = await client.post(
        "/api/v1/users",
        headers=admin_headers,
        # tenant_id is not writable; schema strips it; service stamps from context.
        json={
            "email": email,
            "full_name": "Stamp Me",
            "status": "active",
            "tenant_id": TENANT_B,
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["tenant_id"] == TENANT_A
    assert r.json()["email"] == email


@pytest.mark.asyncio
async def test_cross_tenant_fk_current_behavior(
    client: AsyncClient, admin_headers: dict
):
    """Document current behavior for cross-tenant user_id on orders.

    Postgres FK checks typically bypass RLS on the referenced table, so an order
    in tenant A can reference tenant B's user id. Tenant isolation still stamps
    order.tenant_id from context. Known High if product intent is stricter.
    """
    order_number = f"ORD-XT-{uuid.uuid4().hex[:6]}"
    r = await client.post(
        "/api/v1/orders",
        headers=admin_headers,
        json={
            "user_id": USER_CAROL,
            "order_number": order_number,
            "status": "pending",
            "total_amount": "1.00",
        },
    )
    # Assert current reality (may be 201 with orphan FK or an error).
    assert r.status_code in (201, 400, 409, 500), r.text
    if r.status_code == 201:
        body = r.json()
        assert body["tenant_id"] == TENANT_A
        assert body["user_id"] == USER_CAROL
        # cleanup
        await client.delete(f"/api/v1/orders/{body['id']}", headers=admin_headers)


@pytest.mark.asyncio
async def test_soft_delete_hidden_from_default_list(
    client: AsyncClient, admin_headers: dict
):
    email = f"hide-{uuid.uuid4().hex[:8]}@acme.test"
    r = await client.post(
        "/api/v1/users",
        headers=admin_headers,
        json={"email": email, "full_name": "Hide Me", "status": "active"},
    )
    uid = r.json()["id"]
    await client.delete(f"/api/v1/users/{uid}", headers=admin_headers)

    r = await client.get(
        f"/api/v1/users?filter[email][eq]={email}",
        headers=admin_headers,
    )
    assert r.status_code == 200
    assert r.json()["data"] == []
    assert r.json()["meta"]["total"] == 0

    r = await client.get(f"/api/v1/users/{uid}", headers=admin_headers)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_filter_operators(client: AsyncClient, admin_headers: dict):
    r = await client.get(
        "/api/v1/orders?filter[total_amount][gte]=40&filter[total_amount][lte]=150",
        headers=admin_headers,
    )
    assert r.status_code == 200
    amounts = [float(o["total_amount"]) for o in r.json()["data"]]
    assert amounts
    assert all(40 <= a <= 150 for a in amounts)

    r = await client.get(
        "/api/v1/orders?filter[status][in]=paid,pending&filter[status][ne]=cancelled",
        headers=admin_headers,
    )
    assert r.status_code == 200
    assert {o["status"] for o in r.json()["data"]} <= {"paid", "pending"}

    r = await client.get(
        "/api/v1/orders?filter[order_number][like]=ORD-100%",
        headers=admin_headers,
    )
    assert r.status_code == 200
    assert all(o["order_number"].startswith("ORD-100") for o in r.json()["data"])

    r = await client.get(
        "/api/v1/users?filter[email][ilike]=%ACME.TEST",
        headers=admin_headers,
    )
    assert r.status_code == 200
    assert all("acme.test" in u["email"] for u in r.json()["data"])

    r = await client.get(
        "/api/v1/orders?filter[total_amount][gt]=100&filter[total_amount][lt]=200",
        headers=admin_headers,
    )
    assert r.status_code == 200
    assert all(100 < float(o["total_amount"]) < 200 for o in r.json()["data"])


@pytest.mark.asyncio
async def test_sort_and_pagination_meta(client: AsyncClient, admin_headers: dict):
    r = await client.get(
        "/api/v1/users?sort=-email&limit=1&offset=0",
        headers=admin_headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["meta"]["limit"] == 1
    assert body["meta"]["offset"] == 0
    assert body["meta"]["total"] >= 2
    assert len(body["data"]) == 1

    r2 = await client.get(
        "/api/v1/users?sort=-email&limit=1&offset=1",
        headers=admin_headers,
    )
    assert r2.status_code == 200
    assert r2.json()["data"][0]["email"] != body["data"][0]["email"]

    # max_limit clamp
    r = await client.get("/api/v1/users?limit=1000", headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["meta"]["limit"] == 100


@pytest.mark.asyncio
async def test_invalid_and_nested_include(client: AsyncClient, admin_headers: dict):
    r = await client.get(
        f"/api/v1/users/{USER_ALICE}?include=not_a_relation",
        headers=admin_headers,
    )
    assert r.status_code == 400
    assert r.json()["code"] == "BAD_INCLUDE"

    # Nested path is not a declared relation name → BAD_INCLUDE (depth-1 only).
    r = await client.get(
        f"/api/v1/users/{USER_ALICE}?include=orders.items",
        headers=admin_headers,
    )
    assert r.status_code == 400
    assert r.json()["code"] == "BAD_INCLUDE"


@pytest.mark.asyncio
async def test_include_many_to_one(client: AsyncClient, admin_headers: dict):
    r = await client.get(
        f"/api/v1/orders/{ORDER_ALICE}?include=user",
        headers=admin_headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["user"]["id"] == USER_ALICE
    assert body["user"]["email"] == "alice@acme.test"


@pytest.mark.asyncio
async def test_put_requires_writable_fields_patch_partial(
    client: AsyncClient, admin_headers: dict
):
    email = f"putpatch-{uuid.uuid4().hex[:8]}@acme.test"
    r = await client.post(
        "/api/v1/users",
        headers=admin_headers,
        json={"email": email, "full_name": "Original", "status": "active"},
    )
    uid = r.json()["id"]

    r = await client.put(
        f"/api/v1/users/{uid}",
        headers=admin_headers,
        json={"full_name": "Only Name"},
    )
    assert r.status_code == 400
    assert "detail" in r.json() and "code" in r.json()

    r = await client.patch(
        f"/api/v1/users/{uid}",
        headers=admin_headers,
        json={"full_name": "Patched Only"},
    )
    assert r.status_code == 200
    assert r.json()["full_name"] == "Patched Only"
    assert r.json()["email"] == email
    assert r.json()["status"] == "active"


@pytest.mark.asyncio
async def test_patch_null_skips_field(client: AsyncClient, admin_headers: dict):
    """Current behavior: PATCH null values are dropped so fields stay unchanged."""
    email = f"nullpatch-{uuid.uuid4().hex[:8]}@acme.test"
    r = await client.post(
        "/api/v1/users",
        headers=admin_headers,
        json={"email": email, "full_name": "Keep Name", "status": "active"},
    )
    uid = r.json()["id"]

    r = await client.patch(
        f"/api/v1/users/{uid}",
        headers=admin_headers,
        json={"full_name": None, "status": "inactive"},
    )
    assert r.status_code == 200
    assert r.json()["full_name"] == "Keep Name"
    assert r.json()["status"] == "inactive"


@pytest.mark.asyncio
async def test_upsert_insert_and_nonwritable_ignored(
    client: AsyncClient, admin_headers: dict
):
    email = f"upnew-{uuid.uuid4().hex[:8]}@acme.test"
    r = await client.post(
        "/api/v1/users/upsert",
        headers=admin_headers,
        json={
            "items": [
                {
                    "email": email,
                    "full_name": "Upsert New",
                    "status": "active",
                    "deleted_at": "2020-01-01T00:00:00Z",
                }
            ]
        },
    )
    assert r.status_code == 200, r.text
    row = r.json()[0]
    assert row["email"] == email
    assert row["full_name"] == "Upsert New"
    # deleted_at is not writable / stripped by schema — row is not soft-deleted.
    assert row.get("deleted_at") is None


@pytest.mark.asyncio
async def test_bulk_delete_by_filter(client: AsyncClient, admin_headers: dict):
    tag = uuid.uuid4().hex[:6]
    ids = []
    for i in range(2):
        r = await client.post(
            "/api/v1/users",
            headers=admin_headers,
            json={
                "email": f"bulkf-{tag}-{i}@acme.test",
                "full_name": f"BulkF {i}",
                "status": "inactive",
            },
        )
        assert r.status_code == 201
        ids.append(r.json()["id"])

    r = await client.post(
        "/api/v1/users/bulk-delete",
        headers=admin_headers,
        json={
            "filters": {
                "status": {"eq": "inactive"},
                "email": {"ilike": f"%{tag}%"},
            }
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["deleted"] == 2
    for uid in ids:
        assert (await client.get(f"/api/v1/users/{uid}", headers=admin_headers)).status_code == 404


@pytest.mark.asyncio
async def test_aggregate_count_and_rejects(client: AsyncClient, admin_headers: dict):
    r = await client.post(
        "/api/v1/users/aggregate",
        headers=admin_headers,
        json={"function": "count", "group_by": ["status"]},
    )
    assert r.status_code == 200, r.text
    assert isinstance(r.json()["data"], list)
    assert len(r.json()["data"]) >= 1

    r = await client.post(
        "/api/v1/orders/aggregate",
        headers=admin_headers,
        json={"function": "avg", "field": "total_amount"},
    )
    assert r.status_code == 400
    assert r.json()["code"] == "AGG_DENIED"

    r = await client.post(
        "/api/v1/orders/aggregate",
        headers=admin_headers,
        json={"function": "sum", "field": "order_number"},
    )
    assert r.status_code == 400
    assert r.json()["code"] == "SUM_DENIED"

    r = await client.post(
        "/api/v1/orders/aggregate",
        headers=admin_headers,
        json={"function": "count", "group_by": ["order_number"]},
    )
    assert r.status_code == 400
    assert r.json()["code"] == "GROUP_DENIED"


@pytest.mark.asyncio
async def test_unknown_resource_404(client: AsyncClient, admin_headers: dict):
    r = await client.get("/api/v1/widgets", headers=admin_headers)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_admin_can_create_update_delete(client: AsyncClient, admin_headers: dict):
    email = f"adminops-{uuid.uuid4().hex[:8]}@acme.test"
    r = await client.post(
        "/api/v1/users",
        headers=admin_headers,
        json={"email": email, "full_name": "Ops", "status": "active"},
    )
    assert r.status_code == 201
    uid = r.json()["id"]

    r = await client.patch(
        f"/api/v1/users/{uid}",
        headers=admin_headers,
        json={"status": "inactive"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "inactive"

    r = await client.delete(f"/api/v1/users/{uid}", headers=admin_headers)
    assert r.status_code == 200
