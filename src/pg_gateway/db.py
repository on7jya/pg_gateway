from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

import asyncpg

from pg_gateway.context import get_request_context


class Database:
    def __init__(self, dsn: str, *, statement_timeout_ms: int = 5000) -> None:
        self.dsn = dsn
        self.statement_timeout_ms = statement_timeout_ms
        self.pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        self.pool = await asyncpg.create_pool(
            dsn=self.dsn,
            min_size=1,
            max_size=10,
            command_timeout=max(self.statement_timeout_ms / 1000.0, 1.0),
            init=self._init_conn,
        )

    async def _init_conn(self, conn: asyncpg.Connection) -> None:
        await conn.execute(f"SET statement_timeout = {int(self.statement_timeout_ms)}")

    async def disconnect(self) -> None:
        if self.pool is not None:
            await self.pool.close()
            self.pool = None

    def require_pool(self) -> asyncpg.Pool:
        if self.pool is None:
            raise RuntimeError("database pool not initialized")
        return self.pool

    async def _apply_rls_tenant(self, conn: asyncpg.Connection) -> None:
        """Bind Postgres session GUC for RLS policies (transaction-local)."""
        ctx = get_request_context()
        tenant = ctx.tenant_id or ""
        await conn.execute("SELECT set_config('app.tenant_id', $1, true)", tenant)

    @asynccontextmanager
    async def acquire(self) -> AsyncIterator[asyncpg.Connection]:
        """Connection + transaction with app.tenant_id set for RLS."""
        pool = self.require_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                await self._apply_rls_tenant(conn)
                yield conn

    async def fetch(self, sql: str, *args: object) -> list[asyncpg.Record]:
        async with self.acquire() as conn:
            return await conn.fetch(sql, *args)

    async def fetchrow(self, sql: str, *args: object) -> asyncpg.Record | None:
        async with self.acquire() as conn:
            return await conn.fetchrow(sql, *args)

    async def fetchval(self, sql: str, *args: object) -> object:
        async with self.acquire() as conn:
            return await conn.fetchval(sql, *args)

    async def execute(self, sql: str, *args: object) -> str:
        async with self.acquire() as conn:
            return await conn.execute(sql, *args)
