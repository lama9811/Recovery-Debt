"""SHAP integrity — load-bearing invariant from CLAUDE.md.

`base_value + Σ contributions ≈ prediction` within 0.01. If this fails, the
explainer was fit on the wrong reference data.
"""

from __future__ import annotations

from tests.test_features import _toy_daily

from ml.explain import explain_one, make_explainer
from ml.features import FEATURE_COLUMNS, build_feature_matrix
from ml.train import train_ridge


def test_shap_integrity() -> None:
    matrix = build_feature_matrix(_toy_daily(n=180))
    result = train_ridge(matrix)
    explainer = make_explainer(result.pipeline, result.X_train)
    # Spot-check 10 rows
    for i in range(0, len(matrix), max(1, len(matrix) // 10)):
        row = matrix[FEATURE_COLUMNS].iloc[i]
        ep = explain_one(result.pipeline, explainer, FEATURE_COLUMNS, row)
        assert ep.integrity_residual() < 0.01, (
            f"row {i}: residual={ep.integrity_residual():.5f} — "
            "explainer was fit on raw X_train instead of the scaled representation"
        )
