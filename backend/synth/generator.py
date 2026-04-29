"""Synthetic 180-day demo dataset.

Generates one demo user plus correlated daily rows in `recoveries`, `cycles`,
`sleeps`, `workouts`, `checkins`. Idempotent: every per-day table has
`UNIQUE (user_id, day)` so re-running just upserts.

Run with:  python -m synth.generator
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import os
from uuid import UUID

import asyncpg
import numpy as np
from dotenv import load_dotenv

load_dotenv()

DEMO_EMAIL = "demo@recoverydebt.local"
DEMO_TIMEZONE = os.environ.get("USER_TIMEZONE", "America/New_York")


def simulate(n_days: int, seed: int = 42) -> list[dict]:
    """Return n_days of correlated rows ending today.

    Pure: no DB, no clock other than `today`. Same seed → same rows.
    """
    rng = np.random.default_rng(seed)
    today = dt.date.today()
    days = [today - dt.timedelta(days=i) for i in range(n_days - 1, -1, -1)]

    baseline_hrv = 55.0
    chronic_sleep_debt = 0.0
    yesterday_strain = 11.0
    yesterday_alcohol = 0
    rows: list[dict] = []

    for day in days:
        weekday = day.weekday()
        weekend = weekday in (5, 6)

        # Daily check-in
        alcohol = int(rng.poisson(0.7) if weekend else rng.poisson(0.18))
        alcohol = min(alcohol, 6)
        caffeine = int(np.clip(rng.normal(190, 45), 0, 500))
        stress = int(np.clip(rng.normal(5.0, 1.6), 1, 10))
        late_meal = bool(rng.random() < 0.18)
        ill = bool(rng.random() < 0.03)
        traveling = bool(rng.random() < 0.05)

        # Sleep — pulled down by stress, alcohol, late meals
        sleep_target = (
            7.7
            - 0.45 * (stress >= 8)
            - 0.4 * (alcohol > 0)
            - 0.2 * late_meal
            - 0.3 * traveling
        )
        sleep_h = float(np.clip(rng.normal(sleep_target, 0.75), 4.5, 10.5))
        sleep_total_ms = int(sleep_h * 3_600_000)
        awake_ms = int(np.clip(rng.normal(22, 9), 5, 90) * 60_000)
        in_bed_ms = sleep_total_ms + awake_ms
        deep_frac = float(np.clip(rng.normal(0.16, 0.04), 0.05, 0.3))
        rem_frac = float(np.clip(rng.normal(0.22, 0.04), 0.08, 0.35))
        deep_ms = int(sleep_total_ms * deep_frac)
        rem_ms = int(sleep_total_ms * rem_frac)
        light_ms = max(0, sleep_total_ms - deep_ms - rem_ms)
        efficiency = float(np.clip(100 * sleep_total_ms / max(in_bed_ms, 1), 70, 99))
        consistency = float(np.clip(rng.normal(78, 8), 40, 99))
        resp_rate = float(np.clip(rng.normal(15.5, 0.8), 12, 20))
        sleep_need_ms = int(rng.normal(8.0, 0.3) * 3_600_000)
        disturbances = int(np.clip(rng.normal(8, 4), 0, 30))

        # Strain — lower on weekends, slightly higher on low-stress days
        strain = float(
            np.clip(
                rng.normal(
                    11.0 - (2.5 if weekend else 0) + (0.4 if stress < 4 else 0),
                    3.5,
                ),
                0,
                21,
            )
        )
        kilojoule = float(np.clip(strain * 1100 + rng.normal(0, 500), 0, 30_000))
        avg_hr = int(np.clip(rng.normal(85, 6), 60, 130))
        max_hr = int(np.clip(rng.normal(155, 10), 110, 195))

        # HRV — driven by sleep, yesterday's strain, alcohol, stress, chronic debt
        hrv = (
            baseline_hrv
            + 6.0 * (sleep_h - 7.5)
            - 1.1 * (yesterday_strain - 11.0)
            - 8.0 * (yesterday_alcohol > 0)
            - 4.0 * (alcohol > 0)
            - 0.4 * stress
            - 6.0 * ill
            - chronic_sleep_debt
            + rng.normal(0, 4)
        )
        hrv = float(np.clip(hrv, 18, 110))
        rhr = int(np.clip(60 - 0.2 * (hrv - 55) + rng.normal(0, 3), 38, 90))
        spo2 = float(np.clip(rng.normal(96.5, 0.7), 90, 99.5))
        skin_temp = float(np.clip(rng.normal(34.0, 0.4) + 0.3 * ill, 32, 37))

        # Recovery — mostly HRV-driven, alcohol punches a visible hole
        recovery = (
            50
            + 0.55 * (hrv - 55)
            + 4.5 * (sleep_h - 7.5)
            - 11.0 * (alcohol > 0)
            - 0.7 * (yesterday_strain - 11.0)
            - 1.3 * stress
            - 6.0 * ill
            - 4.0 * traveling
            + rng.normal(0, 4)
        )
        recovery_int = int(np.clip(round(recovery), 0, 100))

        # Roll latent state forward
        chronic_sleep_debt = 0.92 * chronic_sleep_debt + 0.05 * max(0.0, 7.5 - sleep_h)
        yesterday_strain = strain
        yesterday_alcohol = alcohol

        rows.append(
            {
                "day": day,
                "alcohol": alcohol,
                "caffeine": caffeine,
                "stress": stress,
                "late_meal": late_meal,
                "ill": ill,
                "traveling": traveling,
                "sleep_h": sleep_h,
                "in_bed_ms": in_bed_ms,
                "awake_ms": awake_ms,
                "deep_ms": deep_ms,
                "rem_ms": rem_ms,
                "light_ms": light_ms,
                "efficiency": efficiency,
                "consistency": consistency,
                "resp_rate": resp_rate,
                "sleep_need_ms": sleep_need_ms,
                "disturbances": disturbances,
                "strain": strain,
                "kilojoule": kilojoule,
                "avg_hr": avg_hr,
                "max_hr": max_hr,
                "hrv": hrv,
                "rhr": rhr,
                "spo2": spo2,
                "skin_temp": skin_temp,
                "recovery": recovery_int,
            }
        )

    return rows


async def ensure_demo_user(conn: asyncpg.Connection) -> UUID:
    row = await conn.fetchrow("SELECT id FROM users WHERE email = $1", DEMO_EMAIL)
    if row:
        return row["id"]
    return await conn.fetchval(
        "INSERT INTO users (email, timezone) VALUES ($1, $2) RETURNING id",
        DEMO_EMAIL,
        DEMO_TIMEZONE,
    )


async def upsert_rows(conn: asyncpg.Connection, user_id: UUID, rows: list[dict]) -> None:
    async with conn.transaction():
        for r in rows:
            await conn.execute(
                """
                INSERT INTO recoveries
                  (user_id, day, recovery_score, hrv_rmssd_ms, rhr_bpm, spo2_pct,
                   skin_temp_c, score_state)
                VALUES ($1,$2,$3,$4,$5,$6,$7,'SCORED')
                ON CONFLICT (user_id, day) DO UPDATE SET
                  recovery_score = EXCLUDED.recovery_score,
                  hrv_rmssd_ms   = EXCLUDED.hrv_rmssd_ms,
                  rhr_bpm        = EXCLUDED.rhr_bpm,
                  spo2_pct       = EXCLUDED.spo2_pct,
                  skin_temp_c    = EXCLUDED.skin_temp_c
                """,
                user_id, r["day"], r["recovery"], r["hrv"], r["rhr"], r["spo2"],
                r["skin_temp"],
            )
            await conn.execute(
                """
                INSERT INTO cycles
                  (user_id, day, strain, kilojoule, avg_hr_bpm, max_hr_bpm, score_state)
                VALUES ($1,$2,$3,$4,$5,$6,'SCORED')
                ON CONFLICT (user_id, day) DO UPDATE SET
                  strain     = EXCLUDED.strain,
                  kilojoule  = EXCLUDED.kilojoule,
                  avg_hr_bpm = EXCLUDED.avg_hr_bpm,
                  max_hr_bpm = EXCLUDED.max_hr_bpm
                """,
                user_id, r["day"], r["strain"], r["kilojoule"], r["avg_hr"], r["max_hr"],
            )
            await conn.execute(
                """
                INSERT INTO sleeps
                  (user_id, day, in_bed_ms, awake_ms, light_ms, deep_ms, rem_ms,
                   efficiency_pct, consistency_pct, respiratory_rate, sleep_need_ms,
                   disturbances, score_state)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,'SCORED')
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
                  disturbances     = EXCLUDED.disturbances
                """,
                user_id, r["day"], r["in_bed_ms"], r["awake_ms"], r["light_ms"],
                r["deep_ms"], r["rem_ms"], r["efficiency"], r["consistency"],
                r["resp_rate"], r["sleep_need_ms"], r["disturbances"],
            )
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
                  traveling      = EXCLUDED.traveling
                """,
                user_id, r["day"], r["alcohol"], r["caffeine"], r["stress"],
                r["late_meal"], r["ill"], r["traveling"],
            )


async def main(n_days: int, seed: int) -> None:
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        raise SystemExit("DATABASE_URL is not set")
    rows = simulate(n_days, seed=seed)
    conn = await asyncpg.connect(dsn)
    try:
        user_id = await ensure_demo_user(conn)
        await upsert_rows(conn, user_id, rows)
    finally:
        await conn.close()
    print(
        f"seeded user={user_id} days={len(rows)} "
        f"first={rows[0]['day']} last={rows[-1]['day']}"
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--days", type=int, default=180)
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()
    asyncio.run(main(args.days, args.seed))
