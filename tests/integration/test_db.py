from __future__ import annotations

import pytest

from pg_gateway.db import Database

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_db_execute(database_url):
    db = Database(database_url)
    await db.connect()
    try:
        assert await db.execute("SELECT 1") == "SELECT 1"
    finally:
        await db.disconnect()


@pytest.mark.asyncio
async def test_db_connect_disconnect_and_require_pool(database_url):
    db = Database(database_url)
    await db.connect()
    try:
        assert db.require_pool() is not None
    finally:
        await db.disconnect()
    assert db.pool is None
