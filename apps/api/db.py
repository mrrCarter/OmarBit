import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from psycopg import AsyncConnection
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool, PoolTimeout

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://omarbit:omarbit@localhost:5432/omarbit")
DB_POOL_MIN_SIZE = int(os.getenv("DB_POOL_MIN_SIZE", "1"))
DB_POOL_MAX_SIZE = int(os.getenv("DB_POOL_MAX_SIZE", "10"))
DB_POOL_TIMEOUT_SEC = float(os.getenv("DB_POOL_TIMEOUT_SEC", "8"))
DB_POOL_INIT_TIMEOUT_SEC = float(os.getenv("DB_POOL_INIT_TIMEOUT_SEC", "30"))
DB_CONNECT_TIMEOUT_SEC = int(os.getenv("DB_CONNECT_TIMEOUT_SEC", "5"))
DB_STRICT_STARTUP = os.getenv("DB_STRICT_STARTUP", "false").lower() == "true"

_pool: AsyncConnectionPool | None = None


class DatabaseUnavailableError(RuntimeError):
    """Raised when the Postgres pool cannot provide a connection."""


async def init_pool() -> None:
    global _pool
    _pool = AsyncConnectionPool(
        conninfo=DATABASE_URL,
        kwargs={"connect_timeout": DB_CONNECT_TIMEOUT_SEC},
        min_size=DB_POOL_MIN_SIZE,
        max_size=DB_POOL_MAX_SIZE,
        timeout=DB_POOL_TIMEOUT_SEC,
        open=False,
    )
    # Start serving immediately in dev if Postgres is cold/down.
    # In strict mode, require min_size connections before startup succeeds.
    await _pool.open(wait=False)
    if DB_STRICT_STARTUP:
        try:
            await _pool.wait(timeout=DB_POOL_INIT_TIMEOUT_SEC)
        except PoolTimeout as exc:
            await close_pool()
            raise DatabaseUnavailableError(
                f"Database pool initialization timed out after {DB_POOL_INIT_TIMEOUT_SEC:.1f}s"
            ) from exc


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


@asynccontextmanager
async def get_conn() -> AsyncGenerator[AsyncConnection, None]:
    if _pool is None:
        raise DatabaseUnavailableError("Database pool not initialized")
    try:
        async with _pool.connection(timeout=DB_POOL_TIMEOUT_SEC) as conn:
            conn.row_factory = dict_row
            yield conn
    except PoolTimeout as exc:
        raise DatabaseUnavailableError("Database connection unavailable") from exc
