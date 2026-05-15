from collections.abc import AsyncIterator

from psycopg_pool import AsyncConnectionPool

from app.config import get_settings

_pool: AsyncConnectionPool | None = None


def get_database_url() -> str:
    return get_settings().database_url


async def get_pool() -> AsyncConnectionPool:
    global _pool
    if _pool is None:
      database_url = get_database_url()
      if not database_url:
          raise RuntimeError("DATABASE_URL is not configured")
      _pool = AsyncConnectionPool(database_url, open=False)
      await _pool.open()
    return _pool


async def connection() -> AsyncIterator:
    pool = await get_pool()
    async with pool.connection() as conn:
        yield conn


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
