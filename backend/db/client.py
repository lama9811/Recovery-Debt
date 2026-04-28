"""Async Postgres pool used by every endpoint that touches the database.

Held as a module-level singleton; opened on FastAPI startup, closed on shutdown.
Endpoints depend on `get_pool()` so request-time lookups stay cheap.
"""

from __future__ import annotations

import os

import asyncpg

_pool: asyncpg.Pool | None = None


async def open_pool() -> asyncpg.Pool:
    global _pool
    if _pool is not None:
        return _pool
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        raise RuntimeError("DATABASE_URL is not set")
    _pool = await asyncpg.create_pool(dsn, min_size=1, max_size=10)
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is None:
        return
    await _pool.close()
    _pool = None


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("DB pool not initialized — open_pool() must run on startup")
    return _pool
