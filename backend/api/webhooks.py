"""Day 4 — WHOOP webhooks.

WHOOP signs every webhook with HMAC-SHA256 keyed on `WHOOP_WEBHOOK_SECRET`. We
verify the signature, then queue a re-pull of the affected user's last 3 days.
The 4 AM cron (workers/safety_net.py) is the safety net for dropped webhooks.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

from db.client import get_pool

router = APIRouter(prefix="/api/whoop", tags=["whoop"])
logger = logging.getLogger("recovery_debt.whoop_webhook")


def _verify_signature(secret: str, body: bytes, header_signature: str) -> bool:
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    # WHOOP sends the digest as plain hex; some implementations prefix `sha256=`
    received = header_signature.removeprefix("sha256=").strip().lower()
    return hmac.compare_digest(expected, received)


@router.post("/webhook")
async def webhook(request: Request, background_tasks: BackgroundTasks) -> dict[str, bool]:
    secret = os.environ.get("WHOOP_WEBHOOK_SECRET", "").strip()
    body = await request.body()
    sig = request.headers.get("X-WHOOP-Signature") or request.headers.get("x-whoop-signature", "")

    # Reject unauthenticated callbacks. In dev, leaving the secret empty disables
    # the gate so you can curl-test the endpoint locally.
    if secret:
        if not sig or not _verify_signature(secret, body, sig):
            raise HTTPException(401, "bad signature")

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(400, "invalid json") from None

    event_type = payload.get("type") or ""
    whoop_user_id = payload.get("user_id")
    if whoop_user_id is None:
        raise HTTPException(400, "missing user_id")

    pool = get_pool()
    async with pool.acquire() as conn:
        user_id = await conn.fetchval(
            "SELECT id FROM users WHERE whoop_user_id = $1", int(whoop_user_id)
        )
        if not user_id:
            # Webhook for a user we don't know — quietly drop.
            return {"ok": True}

    # Schedule the re-pull via FastAPI BackgroundTasks rather than
    # `asyncio.create_task`, which previously orphaned the coroutine — the GC
    # could collect the task mid-run because nothing held a reference to it.
    background_tasks.add_task(_repull_recent, user_id, event_type)
    return {"ok": True}


async def _repull_recent(user_id, event_type: str) -> None:
    # Imported lazily — the webhook route should still load if asyncpg is fine
    # but the ML stack isn't (e.g. minimal deploy).
    from workers.backfill import backfill_user

    pool = get_pool()
    try:
        counts = await backfill_user(pool, user_id, days=3)
        logger.info("webhook re-pull user=%s event=%s counts=%s", user_id, event_type, counts)
    except Exception:
        logger.exception("webhook re-pull failed user=%s event=%s", user_id, event_type)
