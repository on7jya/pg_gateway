from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

from tests.conftest import ORDERS_READER_DN

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_hard_delete_order_item(client: AsyncClient, admin_headers: dict):
    """order_items has soft_delete disabled → hard DELETE (no deleted_at)."""
    from tests.conftest import USER_ALICE

    tag = uuid.uuid4().hex[:6]
    # create an order to attach the item to
    r = await client.post(
        "/api/v1/orders",
        headers=admin_headers,
        json={
            "user_id": USER_ALICE,
            "order_number": f"ORD-HD-{tag}",
            "status": "pending",
            "total_amount": "1.00",
        },
    )
    assert r.status_code == 201, r.text
    order_id = r.json()["id"]

    # create an order_item
    r = await client.post(
        "/api/v1/order_items",
        headers=admin_headers,
        json={"order_id": order_id, "sku": f"SKU-HD-{tag}", "quantity": 1, "unit_price": "1.00"},
    )
    assert r.status_code == 201, r.text
    item_id = r.json()["id"]

    # hard delete
    r = await client.delete(f"/api/v1/order_items/{item_id}", headers=admin_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("deleted") is True
    assert "id" in body

    # hard-deleted: gone immediately
    r = await client.get(f"/api/v1/order_items/{item_id}", headers=admin_headers)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_update_nonexistent_404(client: AsyncClient, admin_headers: dict):
    r = await client.patch(
        f"/api/v1/users/{uuid.uuid4()}",
        headers=admin_headers,
        json={"full_name": "X"},
    )
    assert r.status_code == 404
    assert r.json()["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_delete_nonexistent_404(client: AsyncClient, admin_headers: dict):
    r = await client.delete(f"/api/v1/users/{uuid.uuid4()}", headers=admin_headers)
    assert r.status_code == 404
    assert r.json()["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_batch_heterogeneous_rejected(client: AsyncClient, admin_headers: dict):
    """Heterogeneous batch items are rejected (no NULL for missing NOT NULL cols)."""
    e1 = f"u1-{uuid.uuid4().hex[:6]}@acme.test"
    e2 = f"u2-{uuid.uuid4().hex[:6]}@acme.test"
    r = await client.post(
        "/api/v1/users/batch",
        headers=admin_headers,
        json={
            "items": [
                {"email": e1, "full_name": "U1"},
                {"email": e2, "full_name": "U2", "status": "active"},
            ]
        },
    )
    assert r.status_code == 400
    assert r.json()["code"] == "BATCH_SHAPE_MISMATCH"


@pytest.mark.asyncio
async def test_include_denied_for_related_resource(client: AsyncClient, admin_headers: dict):
    """orders-reader can read orders but has no users grant → include=user denied."""
    r = await client.get("/api/v1/orders", headers=admin_headers)
    orders = r.json()["data"]
    assert orders
    order_id = orders[0]["id"]

    r = await client.get(
        f"/api/v1/orders/{order_id}?include=user",
        headers={"X-Client-Cert-DN": ORDERS_READER_DN},
    )
    assert r.status_code == 403
    assert r.json()["code"] == "AUTHZ_DENIED"
