"""Async Postgres pool used by every endpoint that touches the database.

Held as a module-level singleton; opened on FastAPI startup, closed on shutdown.
Endpoints depend on `get_pool()` so request-time lookups stay cheap.

Why `statement_cache_size=0`:
Supabase's direct host (`db.<ref>.supabase.co:5432`) is IPv6-only on most
networks, and Railway containers don't have reliable IPv6 egress, so on
production we connect through the IPv4 pooler (`*.pooler.supabase.com:6543`)
which runs pgbouncer in transaction mode. asyncpg's prepared-statement cache
is incompatible with transaction-mode pgbouncer (each query may land on a
different backend), so we disable it. Setting this unconditionally is fine —
direct connections just lose a small server-side cache, and we keep one DSN
shape working in both local dev and prod.
"""

from __future__ import annotations

import os
from uuid import UUID

import asyncpg

_pool: asyncpg.Pool | None = None


async def open_pool() -> asyncpg.Pool:
    global _pool
    if _pool is not None:
        return _pool
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        raise RuntimeError("DATABASE_URL is not set")
    _pool = await asyncpg.create_pool(
        dsn,
        min_size=1,
        max_size=10,
        statement_cache_size=0,
    )
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


async def resolve_active_user_id(demo_email: str) -> UUID | None:
    """Pick the user_id every API request operates on.

    Prefers the most-recently-connected real WHOOP user (any user with a row
    in `whoop_tokens`). Falls back to the demo user (synth data) when no
    real account is connected yet. This is the seam where session-based
    auth would replace the inferred user once multi-user support is needed.

    Returns None when neither a connected user nor the demo user exists,
    so callers can choose whether to 404 or initialize on demand.
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT u.id FROM users u
            INNER JOIN whoop_tokens t ON t.user_id = u.id
            ORDER BY u.created_at DESC
            LIMIT 1
            """
        )
        if row:
            return row["id"]
        row = await conn.fetchrow("SELECT id FROM users WHERE email = $1", demo_email)
        return row["id"] if row else None
