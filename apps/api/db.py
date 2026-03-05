import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from psycopg import AsyncConnection
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://omarbit:omarbit@localhost:5432/omarbit")

_pool: AsyncConnectionPool | None = None


async def init_pool() -> None:
    global _pool
    _pool = AsyncConnectionPool(
        conninfo=DATABASE_URL,
        min_size=2,
        max_size=10,
        open=False,
    )
    await _pool.open()


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


@asynccontextmanager
async def get_conn() -> AsyncGenerator[AsyncConnection, None]:
    if _pool is None:
        raise RuntimeError("Database pool not initialized")
    async with _pool.connection() as conn:
        conn.row_factory = dict_row
        yield conn
