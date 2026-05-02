"""Web Push subscription endpoints — Day 15.

The browser registers a `PushSubscription` via `navigator.serviceWorker`, then
POSTs the descriptor here. We persist on `endpoint` (UNIQUE) so re-subscribes
update in place. The `workers/notify_evening.py` cron reads this table.

Demo-user-scoped, like the rest of `api/data.py` — swap `_get_user_id()` for
a session lookup when real auth lands.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from db.client import get_pool

router = APIRouter(prefix="/api/push", tags=["push"])

DEMO_EMAIL = "demo@recoverydebt.local"


async def _get_user_id() -> UUID:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT id FROM users WHERE email = $1", DEMO_EMAIL)
    if not row:
        raise HTTPException(status_code=404, detail="Demo user not found")
    return row["id"]


class SubscribeBody(BaseModel):
    endpoint: str = Field(min_length=1)
    p256dh: str = Field(min_length=1)
    auth: str = Field(min_length=1)


@router.post("/subscribe")
async def subscribe(
    body: SubscribeBody,
    user_agent: str | None = Header(default=None),
) -> dict[str, Any]:
    user_id = await _get_user_id()
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO push_subscriptions
              (user_id, endpoint, p256dh, auth, user_agent)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (endpoint) DO UPDATE SET
              user_id    = EXCLUDED.user_id,
              p256dh     = EXCLUDED.p256dh,
              auth       = EXCLUDED.auth,
              user_agent = EXCLUDED.user_agent
            """,
            user_id,
            body.endpoint,
            body.p256dh,
            body.auth,
            user_agent,
        )
    return {"ok": True}


class UnsubscribeBody(BaseModel):
    endpoint: str = Field(min_length=1)


@router.post("/unsubscribe")
async def unsubscribe(body: UnsubscribeBody) -> dict[str, Any]:
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM push_subscriptions WHERE endpoint = $1", body.endpoint
        )
    return {"ok": True}
