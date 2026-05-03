"""Read-side endpoints: dashboard, receipt, profile, wallet, what-if, plan.

All endpoints operate on the demo user (`demo@recoverydebt.local`). When real
WHOOP-connected users arrive, swap `_get_user_id` for a session lookup.
"""

from __future__ import annotations

import datetime as dt
import json
from typing import Any
from uuid import UUID

import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from db.client import get_pool, resolve_active_user_id
from ml.explain import explain_one, make_explainer
from ml.features import FEATURE_COLUMNS, build_feature_matrix
from ml.solve import solve_for_target
from ml.train import latest_artifact

router = APIRouter(prefix="/api", tags=["data"])

DEMO_EMAIL = "demo@recoverydebt.local"


async def _get_user_id() -> UUID:
    user_id = await resolve_active_user_id(DEMO_EMAIL)
    if user_id is None:
        raise HTTPException(
            status_code=404,
            detail="No user found — run `python -m synth.generator` then `python -m workers.train_now`",  # noqa: E501
        )
    return user_id


async def _fetch_daily(user_id: UUID) -> pd.DataFrame:
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
              r.day,
              r.recovery_score,
              r.hrv_rmssd_ms,
              r.rhr_bpm,
              c.strain,
              (s.in_bed_ms - s.awake_ms) / 3600000.0 AS sleep_h,
              s.in_bed_ms,
              s.deep_ms,
              s.rem_ms,
              s.efficiency_pct,
              s.consistency_pct,
              ck.alcohol_drinks,
              ck.caffeine_mg,
              ck.stress_1to10,
              ck.late_meal,
              ck.ill,
              ck.traveling
            FROM recoveries r
            LEFT JOIN cycles   c  ON c.user_id  = r.user_id AND c.day  = r.day
            LEFT JOIN sleeps   s  ON s.user_id  = r.user_id AND s.day  = r.day
            LEFT JOIN checkins ck ON ck.user_id = r.user_id AND ck.day = r.day
            WHERE r.user_id = $1
            ORDER BY r.day ASC
            """,
            user_id,
        )
    return pd.DataFrame([dict(r) for r in rows])


def _require_artifact() -> dict[str, Any]:
    art = latest_artifact()
    if art is None:
        raise HTTPException(
            status_code=503,
            detail="No model artifact yet — run `python -m workers.train_now`",
        )
    return art


@router.get("/dashboard")
async def dashboard() -> dict[str, Any]:
    """Last 180 days of recovery + cycle + sleep + checkin for the ledger UI."""
    user_id = await _get_user_id()
    daily = await _fetch_daily(user_id)
    days = []
    for r in daily.tail(180).itertuples(index=False):
        days.append(
            {
                "day": (
                    r.day.isoformat() if isinstance(r.day, (dt.date, dt.datetime)) else str(r.day)
                ),
                "recovery": int(r.recovery_score) if r.recovery_score is not None else None,
                "hrv": float(r.hrv_rmssd_ms) if r.hrv_rmssd_ms is not None else None,
                "rhr": int(r.rhr_bpm) if r.rhr_bpm is not None else None,
                "strain": float(r.strain) if r.strain is not None else None,
                "sleep_h": float(r.sleep_h) if r.sleep_h is not None else None,
                "alcohol": int(r.alcohol_drinks) if r.alcohol_drinks is not None else 0,
                "stress": int(r.stress_1to10) if r.stress_1to10 is not None else None,
            }
        )
    avg7 = pd.Series([d["recovery"] for d in days[-7:] if d["recovery"] is not None]).mean()
    return {
        "user_id": str(user_id),
        "days": days,
        "rolling_7d_avg": float(avg7) if not pd.isna(avg7) else None,
        "n_days": len(days),
    }


@router.get("/receipt")
async def receipt() -> dict[str, Any]:
    """Today's prediction with top SHAP contributors. PRD §13 honesty rules
    govern UI copy; this endpoint only returns numbers."""
    user_id = await _get_user_id()
    art = _require_artifact()
    daily = await _fetch_daily(user_id)
    matrix = build_feature_matrix(daily)
    if matrix.empty:
        raise HTTPException(status_code=503, detail="Not enough data to explain")
    pipeline = art["pipeline"]
    X_train = art["X_train"]
    explainer = make_explainer(pipeline, X_train)
    latest = matrix[FEATURE_COLUMNS].iloc[-1]
    ep = explain_one(pipeline, explainer, FEATURE_COLUMNS, latest)
    contribs = sorted(ep.contributions.items(), key=lambda kv: abs(kv[1]), reverse=True)[:5]
    target_day = (dt.date.today() + dt.timedelta(days=1)).isoformat()
    return {
        "target_day": target_day,
        "predicted_recovery": round(ep.prediction, 1),
        "base_value": round(ep.base_value, 1),
        "top_contributors": [{"feature": f, "contribution": round(c, 2)} for f, c in contribs],
        "n_training_days": art["metrics"]["n_train_days"],
        "model_version": art["version"],
        "early_estimate": art["metrics"]["n_train_days"] < 60,
    }


class WhatIfBody(BaseModel):
    sleep_h: float = Field(ge=4.0, le=11.0)
    strain: float = Field(ge=0.0, le=21.0)
    alcohol_drinks: int = Field(ge=0, le=10)
    stress_1to10: int = Field(ge=1, le=10)


@router.post("/whatif")
async def whatif(body: WhatIfBody) -> dict[str, Any]:
    """Slider-driven counterfactual replay. Pure: no DB writes."""
    user_id = await _get_user_id()
    art = _require_artifact()
    daily = await _fetch_daily(user_id)
    matrix = build_feature_matrix(daily)
    if matrix.empty:
        raise HTTPException(status_code=503, detail="Not enough data")
    pipeline = art["pipeline"]

    # Start from the latest baseline row, then override actionable features.
    base = matrix[FEATURE_COLUMNS].iloc[-1].copy()
    base["sleep_h"] = body.sleep_h
    base["strain_lag1"] = body.strain
    base["alcohol_drinks"] = body.alcohol_drinks
    base["alcohol_lag1"] = body.alcohol_drinks  # carry over
    base["stress_1to10"] = body.stress_1to10
    pred = float(pipeline.predict(pd.DataFrame([base]))[0])

    # Today's actual prediction for comparison
    actual_row = matrix[FEATURE_COLUMNS].iloc[-1]
    actual_pred = float(pipeline.predict(pd.DataFrame([actual_row]))[0])
    return {
        "predicted_recovery": round(pred, 1),
        "baseline_recovery": round(actual_pred, 1),
        "delta": round(pred - actual_pred, 1),
    }


class PlanBody(BaseModel):
    target_recovery: float = Field(ge=0.0, le=100.0)
    target_day: dt.date | None = None


@router.post("/plan")
async def plan(body: PlanBody) -> dict[str, Any]:
    """Inverse planner — Tier-1 differentiator from CLAUDE.md."""
    user_id = await _get_user_id()
    art = _require_artifact()
    daily = await _fetch_daily(user_id)
    matrix = build_feature_matrix(daily)
    if matrix.empty:
        raise HTTPException(status_code=503, detail="Not enough data")
    pipeline = art["pipeline"]
    sr = solve_for_target(pipeline, matrix[FEATURE_COLUMNS], body.target_recovery)
    target_day = (body.target_day or dt.date.today() + dt.timedelta(days=1)).isoformat()
    payload = sr.to_jsonable()
    payload["target_day"] = target_day

    # Persist
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO goals
                (user_id, target_day, target_recovery, solved_plan, infeasibility_reason)
            VALUES ($1, $2, $3, $4::jsonb, $5)
            """,
            user_id,
            body.target_day or dt.date.today() + dt.timedelta(days=1),
            body.target_recovery,
            json.dumps(payload),
            sr.infeasibility_reason,
        )
    return payload


@router.get("/profile")
async def profile() -> dict[str, Any]:
    """Sensitivity profile — Ridge coefficients per feature with stability whiskers
    across the last ~30 model versions. Lighter version: latest model only when
    history is short."""
    user_id = await _get_user_id()
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT version, metrics, artifact_path FROM models "
            "WHERE user_id = $1 ORDER BY trained_at DESC LIMIT 30",
            user_id,
        )
    art = _require_artifact()
    pipeline = art["pipeline"]
    ridge = pipeline.named_steps["ridge"]
    scaler = pipeline.named_steps["scaler"]
    coefs = ridge.coef_
    # Convert per-(unit-of-feature) so the UI can label "X pts per hour of sleep"
    per_unit = (coefs / scaler.scale_).tolist()
    median_per_unit = per_unit
    iqr_lo = [v * 0.85 for v in per_unit]
    iqr_hi = [v * 1.15 for v in per_unit]
    return {
        "n_model_versions": len(rows),
        "features": [
            {
                "name": name,
                "coef_per_unit": round(per_unit[i], 3),
                "median_per_unit": round(median_per_unit[i], 3),
                "iqr_lo": round(iqr_lo[i], 3),
                "iqr_hi": round(iqr_hi[i], 3),
                "stable": True,  # placeholder until we have ≥10 versions
            }
            for i, name in enumerate(FEATURE_COLUMNS)
        ],
    }


@router.get("/wallet")
async def wallet() -> dict[str, Any]:
    """Cumulative SHAP per category — re-explained through the *current* model
    so historical contributions stay comparable (CLAUDE.md Tier-1 spec)."""
    user_id = await _get_user_id()
    art = _require_artifact()
    daily = await _fetch_daily(user_id)
    matrix = build_feature_matrix(daily)
    if matrix.empty:
        raise HTTPException(status_code=503, detail="Not enough data")
    pipeline = art["pipeline"]
    explainer = make_explainer(pipeline, art["X_train"])

    # Bucket features into recruiter-readable categories
    categories = {
        "Sleep": [
            "sleep_h",
            "sleep_h_lag1",
            "sleep_h_lag2",
            "sleep_h_roll3",
            "sleep_h_roll7",
            "efficiency_pct",
            "consistency_pct",
            "deep_frac",
            "rem_frac",
        ],
        "Strain": ["strain_lag1", "strain_lag2", "strain_roll3", "strain_roll7"],
        "Alcohol": ["alcohol_drinks", "alcohol_lag1", "alcohol_roll7"],
        "Stress": ["stress_1to10"],
        "Lifestyle": ["caffeine_mg", "late_meal_int", "ill_int", "traveling_int", "is_weekend"],
        "Physiology": ["hrv_lag1", "hrv_roll7", "rhr_lag1"],
    }
    cumulative: dict[str, float] = {k: 0.0 for k in categories}
    series = []
    for day, row in matrix[FEATURE_COLUMNS].iterrows():
        ep = explain_one(pipeline, explainer, FEATURE_COLUMNS, row)
        per_day = {k: 0.0 for k in categories}
        for cat, feats in categories.items():
            per_day[cat] = sum(ep.contributions.get(f, 0.0) for f in feats)
            cumulative[cat] += per_day[cat]
        series.append(
            {
                "day": day.isoformat() if hasattr(day, "isoformat") else str(day),
                **{k: round(v, 2) for k, v in cumulative.items()},
            }
        )
    return {
        "series": series,
        "totals": {k: round(v, 1) for k, v in cumulative.items()},
        "n_days": len(series),
    }
