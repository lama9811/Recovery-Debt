"""Inverse planner — physiological bounds must hold; infeasibility surfaces."""

from __future__ import annotations

from ml.features import build_feature_matrix
from ml.solve import PHYSIOLOGICAL_BOUNDS, solve_for_target
from ml.train import train_ridge
from tests.test_features import _toy_daily


def test_solve_feasible_returns_actions() -> None:
    matrix = build_feature_matrix(_toy_daily(n=180))
    result = train_ridge(matrix)
    sr = solve_for_target(result.pipeline, matrix, target_recovery=60.0)
    # No matter the outcome, every action stays within physiological bounds.
    for a in sr.actions:
        if a.feature in PHYSIOLOGICAL_BOUNDS:
            lo, hi = PHYSIOLOGICAL_BOUNDS[a.feature]
            assert lo - 1e-3 <= a.value <= hi + 1e-3, f"{a.feature}={a.value} outside [{lo},{hi}]"


def test_solve_infeasible_surfaces_reason() -> None:
    matrix = build_feature_matrix(_toy_daily(n=180))
    result = train_ridge(matrix)
    sr = solve_for_target(result.pipeline, matrix, target_recovery=999.0)
    assert not sr.feasible
    assert sr.infeasibility_reason is not None
    assert "Closest reachable" in sr.infeasibility_reason
