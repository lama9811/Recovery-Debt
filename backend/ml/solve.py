"""Inverse planner — Tier-1 differentiator from CLAUDE.md.

Given a target recovery score, solve for the (sleep, strain, alcohol, ...)
values that make the trained Ridge model predict ≥ target. SLSQP on the linear
objective with hard physiological bounds. When infeasible, return the closest
reachable recovery and which constraint hit its bound — never silently degrade.
"""

from __future__ import annotations

import dataclasses
from typing import Any

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from sklearn.pipeline import Pipeline

from ml.features import FEATURE_COLUMNS

# Hard physiological bounds. From CLAUDE.md / PRD §16.
# (lo, hi) per feature; features not listed default to "freeze at baseline".
PHYSIOLOGICAL_BOUNDS: dict[str, tuple[float, float]] = {
    "sleep_h": (5.0, 10.0),
    "strain_lag1": (0.0, 21.0),  # tomorrow's recovery is driven by today's strain
    "alcohol_drinks": (0.0, 0.0),  # drinking more never *helps* recovery; pin at 0
    "alcohol_lag1": (0.0, 0.0),
    "stress_1to10": (1.0, 7.0),  # we let the planner ask for moderate stress
    "late_meal_int": (0.0, 0.0),
    "ill_int": (0.0, 0.0),
    "traveling_int": (0.0, 0.0),
}

# Features the planner is allowed to move. Everything else is frozen at the
# user's recent average and not surfaced in the recommended plan.
ACTIONABLE: list[str] = [
    "sleep_h",
    "strain_lag1",
    "alcohol_drinks",
    "stress_1to10",
    "late_meal_int",
    "ill_int",
    "traveling_int",
]


@dataclasses.dataclass
class PlannedAction:
    feature: str
    value: float
    at_lower_bound: bool
    at_upper_bound: bool


@dataclasses.dataclass
class SolveResult:
    target_recovery: float
    feasible: bool
    achieved_recovery: float
    actions: list[PlannedAction]
    infeasibility_reason: str | None  # human-readable if not feasible

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "target_recovery": self.target_recovery,
            "feasible": self.feasible,
            "achieved_recovery": self.achieved_recovery,
            "actions": [
                {
                    "feature": a.feature,
                    "value": a.value,
                    "at_lower_bound": a.at_lower_bound,
                    "at_upper_bound": a.at_upper_bound,
                }
                for a in self.actions
            ],
            "infeasibility_reason": self.infeasibility_reason,
        }


def _baseline_vector(recent: pd.DataFrame) -> np.ndarray:
    """Use the user's most recent values as the starting point."""
    last = recent.tail(7)
    vec = np.array(
        [float(last[col].mean()) if col in last.columns else 0.0 for col in FEATURE_COLUMNS],
        dtype=float,
    )
    return vec


def solve_for_target(
    pipeline: Pipeline,
    recent_features: pd.DataFrame,
    target_recovery: float,
) -> SolveResult:
    """Solve for actionable features that hit `target_recovery`.

    Strategy: minimize ‖x − baseline‖² over the actionable subset subject to
    `model(x) >= target` and physiological bounds. If the constraint is
    infeasible, drop it and maximize predicted recovery instead — that gives
    "closest reachable" with the bound that pinned us reported.
    """
    baseline = _baseline_vector(recent_features)
    actionable_idx = [FEATURE_COLUMNS.index(f) for f in ACTIONABLE]

    def predict(x: np.ndarray) -> float:
        row = pd.DataFrame([dict(zip(FEATURE_COLUMNS, x, strict=True))])
        return float(pipeline.predict(row)[0])

    bounds = []
    for col in FEATURE_COLUMNS:
        if col in PHYSIOLOGICAL_BOUNDS:
            bounds.append(PHYSIOLOGICAL_BOUNDS[col])
        else:
            bounds.append((float(baseline[FEATURE_COLUMNS.index(col)]),) * 2)

    # Step 1: try to hit target with minimal deviation
    def objective(x):
        diff = x[actionable_idx] - baseline[actionable_idx]
        return float(diff @ diff)

    def grad(x):
        g = np.zeros_like(x)
        g[actionable_idx] = 2 * (x[actionable_idx] - baseline[actionable_idx])
        return g

    constraint = {
        "type": "ineq",
        "fun": lambda x: predict(x) - target_recovery,
    }
    res = minimize(
        objective,
        x0=baseline.copy(),
        method="SLSQP",
        jac=grad,
        bounds=bounds,
        constraints=[constraint],
        options={"maxiter": 200, "ftol": 1e-6},
    )

    achieved = predict(res.x)
    if res.success and achieved >= target_recovery - 0.5:
        return _package(res.x, baseline, achieved, target_recovery, feasible=True, reason=None)

    # Step 2: infeasible — maximize recovery instead, keep bounds
    res2 = minimize(
        lambda x: -predict(x),
        x0=baseline.copy(),
        method="SLSQP",
        bounds=bounds,
        options={"maxiter": 200, "ftol": 1e-6},
    )
    achieved2 = predict(res2.x)
    pinned = _bounds_pinned(res2.x, bounds, actionable_idx)
    reason = (
        f"Target {target_recovery:.0f} not reachable inside physiological bounds. "
        f"Closest reachable is {achieved2:.0f}"
        + (f" (pinned: {', '.join(pinned)})" if pinned else "")
        + "."
    )
    return _package(res2.x, baseline, achieved2, target_recovery, feasible=False, reason=reason)


def _package(
    x: np.ndarray,
    baseline: np.ndarray,
    achieved: float,
    target: float,
    *,
    feasible: bool,
    reason: str | None,
) -> SolveResult:
    actions: list[PlannedAction] = []
    for col in ACTIONABLE:
        i = FEATURE_COLUMNS.index(col)
        v = float(x[i])
        b = baseline[i]
        if abs(v - b) < 1e-3:
            continue  # don't surface no-op actions
        lo, hi = PHYSIOLOGICAL_BOUNDS.get(col, (-np.inf, np.inf))
        actions.append(
            PlannedAction(
                feature=col,
                value=v,
                at_lower_bound=v <= lo + 1e-3,
                at_upper_bound=v >= hi - 1e-3,
            )
        )
    return SolveResult(
        target_recovery=float(target),
        feasible=feasible,
        achieved_recovery=float(achieved),
        actions=actions,
        infeasibility_reason=reason,
    )


def _bounds_pinned(
    x: np.ndarray,
    bounds: list[tuple[float, float]],
    idxs: list[int],
) -> list[str]:
    pinned = []
    for i in idxs:
        lo, hi = bounds[i]
        if abs(x[i] - lo) < 1e-3 or abs(x[i] - hi) < 1e-3:
            pinned.append(FEATURE_COLUMNS[i])
    return pinned
