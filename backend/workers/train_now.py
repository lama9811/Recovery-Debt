"""Manual end-to-end retrain — Day 10's nightly cron, callable on demand.

Reads the demo user's data from Supabase, builds the feature matrix, trains
Ridge, fits the SHAP explainer, persists the artifact, then writes
`predictions` + `shap_values` for tomorrow.

Run with:  python -m workers.train_now
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import os
from uuid import UUID

import asyncpg
import pandas as pd
from dotenv import load_dotenv

from ml.explain import explain_one, make_explainer
from ml.features import FEATURE_COLUMNS, build_feature_matrix
from ml.train import save_artifact, train_ridge

load_dotenv()


DEMO_EMAIL = "demo@recoverydebt.local"


async def fetch_daily(conn: asyncpg.Connection, user_id: UUID) -> pd.DataFrame:
    """Join the per-day tables we need into one frame."""
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


async def main() -> None:
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        raise SystemExit("DATABASE_URL is not set")
    conn = await asyncpg.connect(dsn)
    try:
        user_id = await conn.fetchval("SELECT id FROM users WHERE email = $1", DEMO_EMAIL)
        if user_id is None:
            raise SystemExit("Demo user not found — run `python -m synth.generator` first")

        daily = await fetch_daily(conn, user_id)
        print(f"daily rows: {len(daily)}")

        matrix = build_feature_matrix(daily)
        print(f"feature matrix: {matrix.shape}")

        result = train_ridge(matrix)
        print(f"metrics: {json.dumps(result.metrics, indent=2)}")

        version = dt.datetime.utcnow().strftime("v%Y%m%d_%H%M%S")
        path = save_artifact(result, version)
        print(f"artifact: {path}")

        await conn.execute(
            """
            INSERT INTO models (user_id, version, n_training_days, metrics, artifact_path)
            VALUES ($1, $2, $3, $4::jsonb, $5)
            ON CONFLICT (user_id, version) DO UPDATE SET
              n_training_days = EXCLUDED.n_training_days,
              metrics         = EXCLUDED.metrics,
              artifact_path   = EXCLUDED.artifact_path
            """,
            user_id,
            version,
            int(result.metrics["n_train_days"]),
            json.dumps(result.metrics),
            str(path),
        )

        # Predict + explain "tomorrow" using the latest feature row
        latest_row = matrix[FEATURE_COLUMNS].iloc[-1]
        explainer = make_explainer(result.pipeline, result.X_train)
        ep = explain_one(result.pipeline, explainer, FEATURE_COLUMNS, latest_row)
        residual = ep.integrity_residual()
        print(f"prediction={ep.prediction:.2f} base={ep.base_value:.2f} |residual|={residual:.4f}")
        if residual > 0.01:
            raise SystemExit(
                f"SHAP integrity check failed (residual={residual:.4f}) — "
                "explainer was fit on the wrong reference data"
            )

        target_day = dt.date.today() + dt.timedelta(days=1)
        prediction_id = await conn.fetchval(
            """
            INSERT INTO predictions (user_id, target_day, predicted_recovery, model_version)
            VALUES ($1, $2, $3, $4)
            RETURNING id
            """,
            user_id,
            target_day,
            ep.prediction,
            version,
        )
        # Wipe old shap rows for this prediction (idempotency on rerun)
        await conn.execute("DELETE FROM shap_values WHERE prediction_id = $1", prediction_id)
        async with conn.transaction():
            for feat, contrib in ep.contributions.items():
                await conn.execute(
                    """
                    INSERT INTO shap_values (prediction_id, feature_name, contribution, base_value)
                    VALUES ($1, $2, $3, $4)
                    """,
                    prediction_id,
                    feat,
                    float(contrib),
                    float(ep.base_value),
                )
        print(f"wrote prediction {prediction_id} for {target_day}")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
