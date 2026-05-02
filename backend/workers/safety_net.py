"""Day 4 — 4 AM safety-net cron.

For every WHOOP-connected user, re-pull the last 3 days. Catches any webhook
that didn't fire and any record that was rescored after the initial backfill.

Railway cron schedule: `0 4 * * *` (4 AM, container's TZ).

Run with:  python -m workers.safety_net
"""

from __future__ import annotations

import asyncio
import logging
import os

import asyncpg
from dotenv import load_dotenv

from workers.backfill import backfill_user

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("recovery_debt.safety_net")


async def main() -> None:
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        raise SystemExit("DATABASE_URL is not set")
    conn = await asyncpg.connect(dsn)
    try:
        rows = await conn.fetch(
            "SELECT u.id, u.email FROM users u JOIN whoop_tokens t ON t.user_id = u.id"
        )
        for row in rows:
            user_id = row["id"]
            try:
                counts = await backfill_user(conn, user_id, days=3)
                logger.info("safety_net user=%s email=%s counts=%s", user_id, row["email"], counts)
            except Exception:
                logger.exception("safety_net failed for user=%s", user_id)
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
