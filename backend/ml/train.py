"""Ridge training with TimeSeriesSplit — load-bearing invariant from CLAUDE.md.

Random `train_test_split` / `KFold` would leak the future on this data and is
forbidden. Use `TimeSeriesSplit` so val_idx > train_idx.max() always.
"""

from __future__ import annotations

import dataclasses
import json
import pathlib
import pickle
from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import RidgeCV
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from ml.features import FEATURE_COLUMNS, TARGET

ARTIFACT_DIR = pathlib.Path(__file__).parent / "artifacts"
ARTIFACT_DIR.mkdir(exist_ok=True)


@dataclasses.dataclass
class TrainResult:
    pipeline: Pipeline
    metrics: dict[str, Any]
    X_train: pd.DataFrame  # used to fit the SHAP explainer
    y_train: pd.Series
    feature_columns: list[str]


def train_ridge(matrix: pd.DataFrame, n_splits: int = 5) -> TrainResult:
    """Fit `StandardScaler -> RidgeCV` on the held-out tail.

    Parameters
    ----------
    matrix : pd.DataFrame
        Output of `build_feature_matrix`. Must contain FEATURE_COLUMNS + TARGET
        and be sorted ascending by day (the index).
    n_splits : int
        TimeSeriesSplit splits. With ~180 days, 5 splits gives a ~30-day val
        window — enough signal without starving training.
    """
    X = matrix[FEATURE_COLUMNS]
    y = matrix[TARGET].astype(float)

    pipeline = Pipeline(
        steps=[
            ("scaler", StandardScaler()),
            (
                "ridge",
                RidgeCV(alphas=np.logspace(-2, 3, 24), cv=TimeSeriesSplit(n_splits=n_splits)),
            ),
        ]
    )
    pipeline.fit(X, y)

    # Held-out tail: final TimeSeriesSplit fold for honest reporting.
    splitter = TimeSeriesSplit(n_splits=n_splits)
    train_idx, val_idx = list(splitter.split(X))[-1]
    assert val_idx.min() > train_idx.max(), "TimeSeriesSplit leak — refusing to ship"

    pred = pipeline.predict(X.iloc[val_idx])
    actual = y.iloc[val_idx].values
    rmse = float(np.sqrt(((pred - actual) ** 2).mean()))
    ss_res = float(((actual - pred) ** 2).sum())
    ss_tot = float(((actual - actual.mean()) ** 2).sum())
    r2 = float(1 - ss_res / ss_tot) if ss_tot > 0 else 0.0

    ridge = pipeline.named_steps["ridge"]
    metrics = {
        "n_train_days": int(len(X)),
        "n_val_days": int(len(val_idx)),
        "rmse": rmse,
        "r2": r2,
        "alpha": float(ridge.alpha_),
        "feature_columns": FEATURE_COLUMNS,
    }
    return TrainResult(
        pipeline=pipeline,
        metrics=metrics,
        X_train=X.iloc[train_idx],
        y_train=y.iloc[train_idx],
        feature_columns=FEATURE_COLUMNS,
    )


def save_artifact(result: TrainResult, version: str) -> pathlib.Path:
    path = ARTIFACT_DIR / f"{version}.pkl"
    payload = {
        "pipeline": result.pipeline,
        "metrics": result.metrics,
        "X_train": result.X_train,
        "y_train": result.y_train,
        "feature_columns": result.feature_columns,
        "version": version,
    }
    with open(path, "wb") as fh:
        pickle.dump(payload, fh)
    return path


def load_artifact(version: str) -> dict[str, Any]:
    path = ARTIFACT_DIR / f"{version}.pkl"
    with open(path, "rb") as fh:
        return pickle.load(fh)


def latest_artifact() -> dict[str, Any] | None:
    files = sorted(ARTIFACT_DIR.glob("*.pkl"))
    if not files:
        return None
    with open(files[-1], "rb") as fh:
        return pickle.load(fh)


if __name__ == "__main__":
    # Tiny smoke: requires a feature_matrix.parquet next to this file.
    p = pathlib.Path(__file__).parent / "feature_matrix.parquet"
    if p.exists():
        m = pd.read_parquet(p)
        result = train_ridge(m)
        print(json.dumps(result.metrics, indent=2))
