"""Daily check-in endpoint — Day 6.

15-second form: alcohol, caffeine, stress, late meal, sick, traveling.
Idempotent on (user_id, day): re-submitting today's check-in updates in place.
"""

from __future__ import annotations

import datetime as dt
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from db.client import get_pool

router = APIRouter(prefix="/api/checkin", tags=["checkin"])

DEMO_EMAIL = "demo@recoverydebt.local"


async def _get_user_id() -> UUID:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT id FROM users WHERE email = $1", DEMO_EMAIL)
    if not row:
        raise HTTPException(status_code=404, detail="Demo user not found")
    return row["id"]


class CheckinBody(BaseModel):
    day: dt.date | None = None  # default today
    alcohol_drinks: int = Field(ge=0, le=20, default=0)
    caffeine_mg: int = Field(ge=0, le=1000, default=0)
    stress_1to10: int = Field(ge=1, le=10)
    late_meal: bool = False
    ill: bool = False
    traveling: bool = False


@router.get("")
async def get_today() -> dict[str, Any]:
    user_id = await _get_user_id()
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM checkins WHERE user_id = $1 AND day = $2",
            user_id,
            dt.date.today(),
        )
    if not row:
        return {"submitted": False}
    return {"submitted": True, **{k: row[k] for k in row.keys() if k != "id"}}


@router.post("")
async def submit(body: CheckinBody) -> dict[str, Any]:
    user_id = await _get_user_id()
    day = body.day or dt.date.today()
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO checkins
              (user_id, day, alcohol_drinks, caffeine_mg, stress_1to10,
               late_meal, ill, traveling)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
            ON CONFLICT (user_id, day) DO UPDATE SET
              alcohol_drinks = EXCLUDED.alcohol_drinks,
              caffeine_mg    = EXCLUDED.caffeine_mg,
              stress_1to10   = EXCLUDED.stress_1to10,
              late_meal      = EXCLUDED.late_meal,
              ill            = EXCLUDED.ill,
              traveling      = EXCLUDED.traveling,
              updated_at     = NOW()
            """,
            user_id,
            day,
            body.alcohol_drinks,
            body.caffeine_mg,
            body.stress_1to10,
            body.late_meal,
            body.ill,
            body.traveling,
        )
    return {"ok": True, "day": day.isoformat()}
