"""Day 15 — 9 PM evening push notification.

For every push subscription, query tomorrow's prediction and send a Web Push
message. Honors PRD §13 honesty: pre-60-days insights are labeled as early
estimates.

Railway cron schedule: `0 21 * * *` (9 PM, container's TZ). See `CRONS.md`.

Run with:  python -m workers.notify_evening
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import logging
import os
from typing import Any

import asyncpg
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("recovery_debt.notify_evening")


def build_evening_payload(
    *,
    predicted_recovery: float,
    target_day: dt.date,
    n_training_days: int,
) -> dict[str, str]:
    """Build the notification body. Pure — no I/O.

    PRD §13: before 60 days of training data, label as 'early estimate'.
    Phrasing is always observational ('Predicted: X'), never imperative.
    """
    rounded = round(predicted_recovery)
    early_suffix = " (early estimate)" if n_training_days < 60 else ""
    return {
        "title": "Tomorrow's recovery forecast",
        "body": (
            f"Predicted: {rounded}{early_suffix}. "
            "Open the app to see today's receipt."
        ),
        "url": "/",
    }


async def _send_one(
    sub: dict[str, Any],
    payload: dict[str, str],
    vapid_private_key: str,
    vapid_subject: str,
) -> bool:
    """Send a single push. Returns False if the subscription is dead (Gone)."""
    from pywebpush import WebPushException, webpush

    try:
        webpush(
            subscription_info={
                "endpoint": sub["endpoint"],
                "keys": {"p256dh": sub["p256dh"], "auth": sub["auth"]},
            },
            data=json.dumps(payload),
            vapid_private_key=vapid_private_key,
            vapid_claims={"sub": vapid_subject},
        )
        return True
    except WebPushException as exc:
        status = getattr(exc.response, "status_code", None)
        if status in (404, 410):
            return False
        logger.warning("webpush failed endpoint=%s status=%s", sub["endpoint"][:60], status)
        return True


async def main() -> None:
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        raise SystemExit("DATABASE_URL is not set")
    vapid_private_key = os.environ.get("VAPID_PRIVATE_KEY", "").strip()
    vapid_subject = os.environ.get("VAPID_SUBJECT", "").strip()
    if not vapid_private_key or not vapid_subject:
        logger.warning("VAPID_PRIVATE_KEY/VAPID_SUBJECT unset — skipping push send")
        return

    conn = await asyncpg.connect(dsn)
    try:
        rows = await conn.fetch(
            """
            SELECT
              ps.id, ps.user_id, ps.endpoint, ps.p256dh, ps.auth,
              p.predicted_recovery, p.target_day,
              m.n_training_days
            FROM push_subscriptions ps
            JOIN LATERAL (
              SELECT predicted_recovery, target_day, model_version
              FROM predictions
              WHERE user_id = ps.user_id AND target_day >= CURRENT_DATE
              ORDER BY target_day ASC, created_at DESC
              LIMIT 1
            ) p ON TRUE
            LEFT JOIN models m
              ON m.user_id = ps.user_id AND m.version = p.model_version
            """
        )
        sent = 0
        pruned = 0
        for row in rows:
            payload = build_evening_payload(
                predicted_recovery=row["predicted_recovery"],
                target_day=row["target_day"],
                n_training_days=row["n_training_days"] or 0,
            )
            alive = await _send_one(
                dict(row), payload, vapid_private_key, vapid_subject
            )
            if alive:
                sent += 1
            else:
                await conn.execute(
                    "DELETE FROM push_subscriptions WHERE id = $1", row["id"]
                )
                pruned += 1
        logger.info("notify_evening sent=%s pruned=%s total=%s", sent, pruned, len(rows))
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
