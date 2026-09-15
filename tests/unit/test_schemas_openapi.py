from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from pg_gateway.config import Settings, load_config
from pg_gateway.main import create_app
from pg_gateway.schemas import create_create_model, create_response_model
from tests.conftest import CONFIG_PATH


def test_dynamic_create_model_fields():
    cfg = load_config(CONFIG_PATH).resource("users")
    model = create_create_model("users", cfg)
    inst = model(email="x@test.com", full_name="X")
    data = inst.model_dump()
    assert data["email"] == "x@test.com"
    assert "id" not in data


def test_dynamic_response_model_includes_id():
    cfg = load_config(CONFIG_PATH).resource("users")
    model = create_response_model("users", cfg)
    assert "id" in model.model_fields


@pytest.mark.asyncio
async def test_openapi_contains_resource_paths():
    settings = Settings(config_path=str(CONFIG_PATH), database_url="postgresql://x")
    app = create_app(config=load_config(CONFIG_PATH), settings=settings, connect_db=False)
    schema = app.openapi()
    paths = schema["paths"]
    assert "/api/v1/users" in paths
    assert "/api/v1/users/{item_id}" in paths
    assert "/api/v1/users/batch" in paths
    assert "/api/v1/users/upsert" in paths
    assert "/api/v1/users/bulk-delete" in paths
    assert "/api/v1/users/aggregate" in paths
    assert "/api/v1/orders" in paths
    assert "/health" in paths
    assert schema["openapi"].startswith("3.")


@pytest.mark.asyncio
async def test_health_without_db():
    settings = Settings(config_path=str(CONFIG_PATH), database_url="postgresql://x")
    app = create_app(config=load_config(CONFIG_PATH), settings=settings, connect_db=False)
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get("/health")
            assert r.status_code == 200
            assert r.json()["status"] == "ok"
