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
USER_BOB = "a0000000-0000-0000-0000-000000000002"
USER_CAROL = "b0000000-0000-0000-0000-000000000001"
ORDER_ALICE = "c0000000-0000-0000-0000-000000000001"
ORDER_BOB = "c0000000-0000-0000-0000-000000000002"
ORDER_CAROL = "c0000000-0000-0000-0000-000000000003"
TRUST_TOKEN = "demo-trust-token"


def gateway_headers(
    *,
    tenant: str | None = TENANT_A,
    roles: str = "admin",
    token: str | None = TRUST_TOKEN,
) -> dict[str, str]:
    headers: dict[str, str] = {}
    if token is not None:
        headers["X-Gateway-Token"] = token
    if tenant is not None:
        headers["X-Tenant-Id"] = tenant
    if roles:
        headers["X-Roles"] = roles
    return headers


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
        gateway_trust_token=os.getenv("GATEWAY_TRUST_TOKEN", TRUST_TOKEN),
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
    return gateway_headers(roles="admin")


@pytest.fixture
def reader_headers() -> dict[str, str]:
    return gateway_headers(roles="reader")


@pytest.fixture
def tenant_b_headers() -> dict[str, str]:
    return gateway_headers(tenant=TENANT_B, roles="admin")
