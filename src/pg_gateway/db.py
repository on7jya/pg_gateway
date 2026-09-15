from __future__ import annotations

import asyncpg


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

    async def fetch(self, sql: str, *args: object) -> list[asyncpg.Record]:
        pool = self.require_pool()
        async with pool.acquire() as conn:
            return await conn.fetch(sql, *args)

    async def fetchrow(self, sql: str, *args: object) -> asyncpg.Record | None:
        pool = self.require_pool()
        async with pool.acquire() as conn:
            return await conn.fetchrow(sql, *args)

    async def fetchval(self, sql: str, *args: object) -> object:
        pool = self.require_pool()
        async with pool.acquire() as conn:
            return await conn.fetchval(sql, *args)

    async def execute(self, sql: str, *args: object) -> str:
        pool = self.require_pool()
        async with pool.acquire() as conn:
            return await conn.execute(sql, *args)
