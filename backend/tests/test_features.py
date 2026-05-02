"""Guards the load-bearing invariants from CLAUDE.md."""

from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd

from ml.features import FEATURE_COLUMNS, TARGET, build_feature_matrix
from ml.train import train_ridge


def _toy_daily(n: int = 90, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    today = dt.date.today()
    days = [today - dt.timedelta(days=i) for i in range(n - 1, -1, -1)]
    sleep_h = rng.normal(7.5, 0.8, size=n).clip(5, 10)
    strain = rng.normal(11, 3, size=n).clip(0, 21)
    alcohol = rng.poisson(0.3, size=n)
    hrv = 55 + 6 * (sleep_h - 7.5) - 8 * (alcohol > 0) + rng.normal(0, 4, size=n)
    rhr = (60 - 0.2 * (hrv - 55) + rng.normal(0, 2, size=n)).round().astype(int)
    in_bed_ms = (sleep_h * 3.6e6 * 1.08).astype(int)
    deep_ms = (sleep_h * 3.6e6 * 0.16).astype(int)
    rem_ms = (sleep_h * 3.6e6 * 0.22).astype(int)
    recovery = (
        (
            50
            + 0.55 * (hrv - 55)
            + 4.5 * (sleep_h - 7.5)
            - 11 * (alcohol > 0)
            + rng.normal(0, 3, size=n)
        )
        .clip(0, 100)
        .round()
        .astype(int)
    )
    return pd.DataFrame(
        {
            "day": days,
            "recovery_score": recovery,
            "hrv_rmssd_ms": hrv,
            "rhr_bpm": rhr,
            "sleep_h": sleep_h,
            "in_bed_ms": in_bed_ms,
            "deep_ms": deep_ms,
            "rem_ms": rem_ms,
            "efficiency_pct": np.full(n, 92.0),
            "consistency_pct": np.full(n, 78.0),
            "strain": strain,
            "alcohol_drinks": alcohol,
            "caffeine_mg": np.full(n, 180),
            "stress_1to10": np.full(n, 5),
            "late_meal": np.zeros(n, dtype=bool),
            "ill": np.zeros(n, dtype=bool),
            "traveling": np.zeros(n, dtype=bool),
        }
    )


def test_pure() -> None:
    """build_feature_matrix is deterministic — same input → same output, twice."""
    df = _toy_daily()
    m1 = build_feature_matrix(df)
    m2 = build_feature_matrix(df)
    pd.testing.assert_frame_equal(m1, m2)


def test_columns() -> None:
    df = _toy_daily()
    matrix = build_feature_matrix(df)
    assert list(matrix.columns) == FEATURE_COLUMNS + [TARGET]
    assert not matrix.isna().any().any(), "no NaNs may leak into the model"


def test_no_future_leakage() -> None:
    """TimeSeriesSplit places val strictly after train."""
    from sklearn.model_selection import TimeSeriesSplit

    matrix = build_feature_matrix(_toy_daily(n=120))
    splitter = TimeSeriesSplit(n_splits=5)
    for train_idx, val_idx in splitter.split(matrix):
        assert val_idx.min() > train_idx.max(), (
            f"val_idx={val_idx.min()} must be after train_idx.max={train_idx.max()}"
        )


def test_train_runs() -> None:
    matrix = build_feature_matrix(_toy_daily(n=120))
    result = train_ridge(matrix)
    assert result.metrics["n_train_days"] > 60
    assert result.metrics["rmse"] >= 0
    # Don't assert R² — tiny synthetic samples can score negative on the tail.
