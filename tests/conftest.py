from __future__ import annotations

import os
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from pg_gateway.config import Settings, load_config
from pg_gateway.main import create_app

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "config.yaml"

TENANT_A = "11111111-1111-1111-1111-111111111111"
TENANT_B = "22222222-2222-2222-2222-222222222222"
USER_ALICE = "a0000000-0000-0000-0000-000000000001"


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "integration: requires Postgres")


@pytest.fixture(scope="session")
def app_config():
    return load_config(CONFIG_PATH)


@pytest.fixture(scope="session")
def database_url() -> str:
    return os.getenv(
        "DATABASE_URL",
        "postgresql://gateway:gateway@localhost:5432/gateway",
    )


@pytest.fixture(scope="session")
def settings(database_url: str) -> Settings:
    return Settings(
        database_url=database_url,
        config_path=str(CONFIG_PATH),
    )


@pytest_asyncio.fixture
async def app(app_config, settings):
    """Function-scoped app so the asyncpg pool binds to the test event loop."""
    application = create_app(config=app_config, settings=settings, connect_db=True)
    async with application.router.lifespan_context(application):
        yield application


@pytest_asyncio.fixture
async def client(app) -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def admin_headers() -> dict[str, str]:
    return {"X-Tenant-Id": TENANT_A, "X-Roles": "admin"}


@pytest.fixture
def reader_headers() -> dict[str, str]:
    return {"X-Tenant-Id": TENANT_A, "X-Roles": "reader"}


@pytest.fixture
def tenant_b_headers() -> dict[str, str]:
    return {"X-Tenant-Id": TENANT_B, "X-Roles": "admin"}
