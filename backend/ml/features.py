"""Pure feature transform — load-bearing invariant from CLAUDE.md.

`build_feature_matrix` MUST be pure: same input → same output, no DB reads,
no clock, no global state. The inverse planner replays single feature vectors
through the same transform and the SHAP explainer is fit on its output, so any
hidden state silently breaks counterfactuals.

Tests in `tests/test_features.py` guard this.
"""

from __future__ import annotations

import pandas as pd

# Single source of truth for feature ordering. The Ridge pipeline, SHAP
# explainer, and inverse planner all key off this list.
FEATURE_COLUMNS: list[str] = [
    "sleep_h",
    "sleep_h_lag1",
    "sleep_h_lag2",
    "sleep_h_roll3",
    "sleep_h_roll7",
    "efficiency_pct",
    "consistency_pct",
    "deep_frac",
    "rem_frac",
    "strain_lag1",
    "strain_lag2",
    "strain_roll3",
    "strain_roll7",
    "hrv_lag1",
    "hrv_roll7",
    "rhr_lag1",
    "alcohol_drinks",
    "alcohol_lag1",
    "alcohol_roll7",
    "caffeine_mg",
    "stress_1to10",
    "late_meal_int",
    "ill_int",
    "traveling_int",
    "is_weekend",
    "missing_checkin",
    "missing_sleep",
    "missing_strain",
]

TARGET = "recovery_score"


def build_feature_matrix(daily: pd.DataFrame) -> pd.DataFrame:
    """Transform one-row-per-day into a model-ready feature matrix.

    Parameters
    ----------
    daily : pd.DataFrame
        Indexed (or sorted) by `day` ascending. Expected columns:
          recovery_score, hrv_rmssd_ms, rhr_bpm,
          sleep_h, in_bed_ms, deep_ms, rem_ms, efficiency_pct, consistency_pct,
          strain,
          alcohol_drinks, caffeine_mg, stress_1to10, late_meal, ill, traveling
        Missing values are allowed; was_missing flags are emitted.

    Returns
    -------
    pd.DataFrame indexed by day with FEATURE_COLUMNS and TARGET. Rows where
    insufficient lag history is available (first 7 days) are dropped.
    """
    df = daily.copy()
    if "day" in df.columns:
        df = df.sort_values("day").set_index("day")
    else:
        df = df.sort_index()

    # Sleep block
    df["sleep_h_lag1"] = df["sleep_h"].shift(1)
    df["sleep_h_lag2"] = df["sleep_h"].shift(2)
    df["sleep_h_roll3"] = df["sleep_h"].rolling(3, min_periods=1).mean().shift(1)
    df["sleep_h_roll7"] = df["sleep_h"].rolling(7, min_periods=1).mean().shift(1)
    df["deep_frac"] = (df["deep_ms"] / df["in_bed_ms"]).clip(0, 1)
    df["rem_frac"] = (df["rem_ms"] / df["in_bed_ms"]).clip(0, 1)

    # Strain block
    df["strain_lag1"] = df["strain"].shift(1)
    df["strain_lag2"] = df["strain"].shift(2)
    df["strain_roll3"] = df["strain"].rolling(3, min_periods=1).mean().shift(1)
    df["strain_roll7"] = df["strain"].rolling(7, min_periods=1).mean().shift(1)

    # HRV / RHR (lagged so we predict tomorrow without leaking today's HRV)
    df["hrv_lag1"] = df["hrv_rmssd_ms"].shift(1)
    df["hrv_roll7"] = df["hrv_rmssd_ms"].rolling(7, min_periods=1).mean().shift(1)
    df["rhr_lag1"] = df["rhr_bpm"].shift(1)

    # Check-in
    df["alcohol_lag1"] = df["alcohol_drinks"].shift(1)
    df["alcohol_roll7"] = df["alcohol_drinks"].rolling(7, min_periods=1).mean().shift(1)
    df["late_meal_int"] = df["late_meal"].astype("float").fillna(0.0)
    df["ill_int"] = df["ill"].astype("float").fillna(0.0)
    df["traveling_int"] = df["traveling"].astype("float").fillna(0.0)
    df["is_weekend"] = pd.to_datetime(df.index).dayofweek.isin([5, 6]).astype("float")

    # was_missing flags — three coarse bands rather than per-column to keep
    # the model identifiable on small datasets.
    df["missing_checkin"] = (
        df[["alcohol_drinks", "caffeine_mg", "stress_1to10"]].isna().any(axis=1).astype("float")
    )
    df["missing_sleep"] = df["sleep_h"].isna().astype("float")
    df["missing_strain"] = df["strain"].isna().astype("float")

    # Median-impute any remaining NaNs per column (Ridge can't see them).
    for col in FEATURE_COLUMNS:
        if col not in df.columns:
            df[col] = 0.0
        if df[col].isna().any():
            df[col] = df[col].fillna(df[col].median())

    out = df[FEATURE_COLUMNS + [TARGET]].copy()
    # Drop rows where target is missing (can't train) or earliest lags are NaN.
    out = out.dropna(subset=[TARGET])
    return out
