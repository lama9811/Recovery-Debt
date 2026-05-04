"""Day 3 — six-month WHOOP backfill.

Pages through the four per-day endpoints and upserts into Postgres. Idempotent:
the per-day tables all carry `UNIQUE (user_id, day)` so a re-run just refreshes.

Run with:  python -m workers.backfill [--user-email someone@example.com] [--days 180]
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import os
from typing import Any
from uuid import UUID

import asyncpg
import httpx
from dotenv import load_dotenv

load_dotenv()

WHOOP_BASE = "https://api.prod.whoop.com/developer"
WHOOP_TOKEN_URL = "https://api.prod.whoop.com/oauth/oauth2/token"

# Tunable politeness — WHOOP rate-limits aggressively on backfills.
PAGE_LIMIT = 25
PAGE_SLEEP_S = 0.25


async def _refresh_if_needed(
    conn: asyncpg.Connection, user_id: UUID, slack_seconds: int = 120
) -> str:
    """Return a non-expired access token for `user_id`.

    Refreshes via the OAuth refresh_token grant if we're within `slack_seconds`
    of expiry. Updates the `whoop_tokens` row in place.
    """
    row = await conn.fetchrow(
        "SELECT access_token, refresh_token, expires_at FROM whoop_tokens WHERE user_id = $1",
        user_id,
    )
    if not row:
        raise RuntimeError(f"No WHOOP token for user {user_id}")
    expires_at: dt.datetime = row["expires_at"]
    now = dt.datetime.now(dt.UTC)
    if expires_at - now > dt.timedelta(seconds=slack_seconds):
        return row["access_token"]

    client_id = os.environ["WHOOP_CLIENT_ID"].strip()
    client_secret = os.environ["WHOOP_CLIENT_SECRET"].strip()
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            WHOOP_TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": row["refresh_token"],
                "client_id": client_id,
                "client_secret": client_secret,
                "scope": "offline",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    if resp.status_code != 200:
        raise RuntimeError(f"WHOOP refresh failed: {resp.status_code} {resp.text}")
    tokens = resp.json()
    new_access = tokens["access_token"]
    new_refresh = tokens.get("refresh_token", row["refresh_token"])
    expires_in = int(tokens.get("expires_in", 3600))
    new_expires_at = now + dt.timedelta(seconds=expires_in)
    await conn.execute(
        """
        UPDATE whoop_tokens
        SET access_token = $2, refresh_token = $3, expires_at = $4, updated_at = NOW()
        WHERE user_id = $1
        """,
        user_id,
        new_access,
        new_refresh,
        new_expires_at,
    )
    return new_access


def _to_day(iso_ts: str | None) -> dt.date | None:
    if not iso_ts:
        return None
    return dt.datetime.fromisoformat(iso_ts.replace("Z", "+00:00")).date()


async def _paged(client: httpx.AsyncClient, path: str, start_iso: str, end_iso: str):
    next_token: str | None = None
    while True:
        params: dict[str, Any] = {"start": start_iso, "end": end_iso, "limit": PAGE_LIMIT}
        if next_token:
            params["nextToken"] = next_token
        resp = await client.get(f"{WHOOP_BASE}{path}", params=params)
        if resp.status_code == 429:
            # Rate-limited: WHOOP suggests retry-after; default to 5s.
            await asyncio.sleep(float(resp.headers.get("Retry-After", "5")))
            continue
        resp.raise_for_status()
        data = resp.json()
        for rec in data.get("records", []):
            yield rec
        next_token = data.get("next_token")
        if not next_token:
            return
        await asyncio.sleep(PAGE_SLEEP_S)


async def backfill_recoveries(
    conn: asyncpg.Connection,
    client: httpx.AsyncClient,
    user_id: UUID,
    start_iso: str,
    end_iso: str,
) -> int:
    n = 0
    async for rec in _paged(client, "/v2/recovery", start_iso, end_iso):
        score = rec.get("score") or {}
        # Recovery rows are scoped to a sleep/cycle pair; use updated_at's date
        day = _to_day(rec.get("updated_at") or rec.get("created_at"))
        if not day:
            continue
        await conn.execute(
            """
            INSERT INTO recoveries
              (user_id, day, recovery_score, hrv_rmssd_ms, rhr_bpm, spo2_pct,
               skin_temp_c, score_state)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
            ON CONFLICT (user_id, day) DO UPDATE SET
              recovery_score = EXCLUDED.recovery_score,
              hrv_rmssd_ms   = EXCLUDED.hrv_rmssd_ms,
              rhr_bpm        = EXCLUDED.rhr_bpm,
              spo2_pct       = EXCLUDED.spo2_pct,
              skin_temp_c    = EXCLUDED.skin_temp_c,
              score_state    = EXCLUDED.score_state
            """,
            user_id,
            day,
            score.get("recovery_score"),
            score.get("hrv_rmssd_milli"),
            score.get("resting_heart_rate"),
            score.get("spo2_percentage"),
            score.get("skin_temp_celsius"),
            rec.get("score_state"),
        )
        n += 1
    return n


async def backfill_cycles(
    conn: asyncpg.Connection,
    client: httpx.AsyncClient,
    user_id: UUID,
    start_iso: str,
    end_iso: str,
) -> int:
    n = 0
    async for rec in _paged(client, "/v2/cycle", start_iso, end_iso):
        score = rec.get("score") or {}
        day = _to_day(rec.get("start"))
        if not day:
            continue
        await conn.execute(
            """
            INSERT INTO cycles
              (user_id, day, strain, kilojoule, avg_hr_bpm, max_hr_bpm,
               start_ts, end_ts, score_state)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
            ON CONFLICT (user_id, day) DO UPDATE SET
              strain      = EXCLUDED.strain,
              kilojoule   = EXCLUDED.kilojoule,
              avg_hr_bpm  = EXCLUDED.avg_hr_bpm,
              max_hr_bpm  = EXCLUDED.max_hr_bpm,
              start_ts    = EXCLUDED.start_ts,
              end_ts      = EXCLUDED.end_ts,
              score_state = EXCLUDED.score_state
            """,
            user_id,
            day,
            score.get("strain"),
            score.get("kilojoule"),
            score.get("average_heart_rate"),
            score.get("max_heart_rate"),
            rec.get("start"),
            rec.get("end"),
            rec.get("score_state"),
        )
        n += 1
    return n


async def backfill_sleeps(
    conn: asyncpg.Connection,
    client: httpx.AsyncClient,
    user_id: UUID,
    start_iso: str,
    end_iso: str,
) -> int:
    n = 0
    async for rec in _paged(client, "/v2/activity/sleep", start_iso, end_iso):
        score = rec.get("score") or {}
        stage = score.get("stage_summary") or {}
        # v2: sleep_needed is a top-level object inside `score`, with components
        # broken out. Sum the parts so `sleep_need_ms` keeps meaning "the model's
        # baseline-need estimate for this sleep" without changing downstream code.
        needed = score.get("sleep_needed") or {}
        sleep_need_ms = needed.get("baseline_milli")
        day = _to_day(rec.get("end") or rec.get("start"))
        if not day:
            continue
        await conn.execute(
            """
            INSERT INTO sleeps
              (user_id, day, in_bed_ms, awake_ms, light_ms, deep_ms, rem_ms,
               efficiency_pct, consistency_pct, respiratory_rate, sleep_need_ms,
               disturbances, start_ts, end_ts, score_state)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15)
            ON CONFLICT (user_id, day) DO UPDATE SET
              in_bed_ms        = EXCLUDED.in_bed_ms,
              awake_ms         = EXCLUDED.awake_ms,
              light_ms         = EXCLUDED.light_ms,
              deep_ms          = EXCLUDED.deep_ms,
              rem_ms           = EXCLUDED.rem_ms,
              efficiency_pct   = EXCLUDED.efficiency_pct,
              consistency_pct  = EXCLUDED.consistency_pct,
              respiratory_rate = EXCLUDED.respiratory_rate,
              sleep_need_ms    = EXCLUDED.sleep_need_ms,
              disturbances     = EXCLUDED.disturbances,
              start_ts         = EXCLUDED.start_ts,
              end_ts           = EXCLUDED.end_ts,
              score_state      = EXCLUDED.score_state
            """,
            user_id,
            day,
            stage.get("total_in_bed_time_milli"),
            stage.get("total_awake_time_milli"),
            stage.get("total_light_sleep_time_milli"),
            stage.get("total_slow_wave_sleep_time_milli"),
            stage.get("total_rem_sleep_time_milli"),
            score.get("sleep_efficiency_percentage"),
            score.get("sleep_consistency_percentage"),
            score.get("respiratory_rate"),
            sleep_need_ms,
            stage.get("disturbance_count"),
            rec.get("start"),
            rec.get("end"),
            rec.get("score_state"),
        )
        n += 1
    return n


async def backfill_workouts(
    conn: asyncpg.Connection,
    client: httpx.AsyncClient,
    user_id: UUID,
    start_iso: str,
    end_iso: str,
) -> int:
    n = 0
    async for rec in _paged(client, "/v2/activity/workout", start_iso, end_iso):
        score = rec.get("score") or {}
        # v2: id is a UUID string; v1's int id is preserved as `v1_id`.
        whoop_id = rec.get("id")
        day = _to_day(rec.get("start"))
        if not day or whoop_id is None:
            continue
        zones = score.get("zone_durations") or {}
        await conn.execute(
            """
            INSERT INTO workouts
              (user_id, whoop_id, day, start_ts, end_ts, strain, sport_id,
               avg_hr_bpm, max_hr_bpm, kilojoule, distance_m, zone_durations,
               score_state)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12::jsonb,$13)
            ON CONFLICT (user_id, whoop_id) DO UPDATE SET
              day            = EXCLUDED.day,
              start_ts       = EXCLUDED.start_ts,
              end_ts         = EXCLUDED.end_ts,
              strain         = EXCLUDED.strain,
              sport_id       = EXCLUDED.sport_id,
              avg_hr_bpm     = EXCLUDED.avg_hr_bpm,
              max_hr_bpm     = EXCLUDED.max_hr_bpm,
              kilojoule      = EXCLUDED.kilojoule,
              distance_m     = EXCLUDED.distance_m,
              zone_durations = EXCLUDED.zone_durations,
              score_state    = EXCLUDED.score_state
            """,
            user_id,
            str(whoop_id),
            day,
            rec.get("start"),
            rec.get("end"),
            score.get("strain"),
            rec.get("sport_id"),
            score.get("average_heart_rate"),
            score.get("max_heart_rate"),
            score.get("kilojoule"),
            score.get("distance_meter"),
            __import__("json").dumps(zones),
            rec.get("score_state"),
        )
        n += 1
    return n


async def backfill_user(
    pool_or_conn: asyncpg.Pool | asyncpg.Connection,
    user_id: UUID,
    days: int = 180,
) -> dict[str, int]:
    """Pull `days` worth of WHOOP data into the per-day tables.

    Accepts either an asyncpg Pool (preferred — releases connections between
    paged endpoint calls so a single long-held connection can't time out on
    Supabase's transaction-mode pooler) or a Connection (legacy, used by the
    CLI runner). When given a Pool we acquire/release per endpoint; when given
    a Connection we just use it throughout.
    """
    end = dt.datetime.now(dt.UTC)
    start = end - dt.timedelta(days=days)
    start_iso = start.isoformat().replace("+00:00", "Z")
    end_iso = end.isoformat().replace("+00:00", "Z")

    is_pool = isinstance(pool_or_conn, asyncpg.Pool)

    if is_pool:
        async with pool_or_conn.acquire() as conn:
            access_token = await _refresh_if_needed(conn, user_id)
    else:
        access_token = await _refresh_if_needed(pool_or_conn, user_id)

    headers = {"Authorization": f"Bearer {access_token}"}
    async with httpx.AsyncClient(headers=headers, timeout=30.0) as client:
        async def _run(fn):
            if is_pool:
                async with pool_or_conn.acquire() as conn:
                    return await fn(conn, client, user_id, start_iso, end_iso)
            return await fn(pool_or_conn, client, user_id, start_iso, end_iso)

        n_recoveries = await _run(backfill_recoveries)
        n_cycles = await _run(backfill_cycles)
        n_sleeps = await _run(backfill_sleeps)
        n_workouts = await _run(backfill_workouts)

    return {
        "recoveries": n_recoveries,
        "cycles": n_cycles,
        "sleeps": n_sleeps,
        "workouts": n_workouts,
    }


async def main(email: str | None, days: int) -> None:
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        raise SystemExit("DATABASE_URL is not set")
    conn = await asyncpg.connect(dsn)
    try:
        if email:
            user_id = await conn.fetchval("SELECT id FROM users WHERE email = $1", email)
        else:
            user_id = await conn.fetchval(
                """
                SELECT u.id FROM users u
                JOIN whoop_tokens t ON t.user_id = u.id
                ORDER BY t.updated_at DESC
                LIMIT 1
                """
            )
        if not user_id:
            raise SystemExit("No WHOOP-connected user found. Click 'Connect WHOOP' first.")
        counts = await backfill_user(conn, user_id, days=days)
        print(f"backfilled user={user_id} {counts}")
    finally:
        await conn.close()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--user-email", default=None)
    p.add_argument("--days", type=int, default=180)
    args = p.parse_args()
    asyncio.run(main(args.user_email, args.days))
