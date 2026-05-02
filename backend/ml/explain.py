"""SHAP explainer — load-bearing invariant from CLAUDE.md.

`shap.LinearExplainer` is exact for Ridge. Critical: fit it on the *scaled*
training data (`pipeline[:-1].transform(X_train)`), not raw `X_train`. Fitting
on raw data makes `base_value + Σ contributions` not equal the prediction —
the SHAP integrity test will catch this.
"""

from __future__ import annotations

import dataclasses

import numpy as np
import pandas as pd
import shap
from sklearn.pipeline import Pipeline


@dataclasses.dataclass
class ExplainedPrediction:
    prediction: float
    base_value: float
    contributions: dict[str, float]  # feature_name -> contribution

    def integrity_residual(self) -> float:
        return abs(self.base_value + sum(self.contributions.values()) - self.prediction)


def make_explainer(pipeline: Pipeline, X_train: pd.DataFrame) -> shap.LinearExplainer:
    """Build a LinearExplainer keyed to the trained Ridge model.

    Reference data MUST be the post-scaler representation — anything else
    breaks the Ridge linearity guarantee that SHAP relies on.
    """
    ridge = pipeline.named_steps["ridge"]
    pre = pipeline[:-1]  # scaler-only sub-pipeline
    X_scaled = pre.transform(X_train)
    return shap.LinearExplainer(ridge, X_scaled)


def explain_one(
    pipeline: Pipeline,
    explainer: shap.LinearExplainer,
    feature_columns: list[str],
    x: pd.Series | dict | np.ndarray,
) -> ExplainedPrediction:
    """Explain a single prediction.

    Parameters
    ----------
    x : Series, dict, or 1-D array aligned to feature_columns.
    """
    if isinstance(x, dict):
        row = pd.DataFrame([{c: x.get(c, 0.0) for c in feature_columns}])
    elif isinstance(x, pd.Series):
        row = pd.DataFrame([x.reindex(feature_columns).to_dict()])
    else:
        arr = np.asarray(x).reshape(1, -1)
        row = pd.DataFrame(arr, columns=feature_columns)

    pred = float(pipeline.predict(row)[0])
    pre = pipeline[:-1]
    x_scaled = pre.transform(row)
    sv = explainer.shap_values(x_scaled)
    sv = np.asarray(sv).reshape(-1)
    base = float(np.asarray(explainer.expected_value).reshape(-1)[0])

    contributions = {col: float(sv[i]) for i, col in enumerate(feature_columns)}
    return ExplainedPrediction(
        prediction=pred,
        base_value=base,
        contributions=contributions,
    )
