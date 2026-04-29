"use client";

import { useState } from "react";

import { Nav } from "@/components/Nav";
import { apiPost } from "@/lib/api";

type PlanAction = {
  feature: string;
  value: number;
  at_lower_bound: boolean;
  at_upper_bound: boolean;
};

type PlanResp = {
  target_recovery: number;
  feasible: boolean;
  achieved_recovery: number;
  actions: PlanAction[];
  infeasibility_reason: string | null;
  target_day: string;
};

const FEATURE_DESC: Record<string, (v: number) => string> = {
  sleep_h: (v) => `Sleep ${v.toFixed(1)} hours`,
  strain_lag1: (v) => `Keep strain near ${v.toFixed(1)}`,
  alcohol_drinks: (v) => (v < 0.5 ? "Skip alcohol" : `Alcohol ≤ ${Math.round(v)}`),
  alcohol_lag1: (v) => (v < 0.5 ? "Skip alcohol the day before" : ""),
  stress_1to10: (v) => `Stress ≤ ${Math.round(v)}/10`,
  late_meal_int: (v) => (v < 0.5 ? "No late meal" : ""),
  ill_int: () => "",
  traveling_int: (v) => (v < 0.5 ? "No travel" : ""),
};

export default function Plan() {
  const [target, setTarget] = useState(75);
  const [resp, setResp] = useState<PlanResp | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    setPending(true);
    setError(null);
    try {
      const r = await apiPost<PlanResp>("/api/plan", {
        target_recovery: target,
      });
      setResp(r);
    } catch (e) {
      setError(String(e));
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="flex min-h-screen flex-col">
      <Nav />
      <main className="flex-1 px-10 pb-24">
        <div className="mx-auto max-w-3xl">
          <div className="mb-8">
            <span className="rd-eyebrow">Inverse Planner</span>
            <h1 className="rd-h1 text-[40px] mt-3">
              Solve for the recovery you want.
            </h1>
            <p className="mt-3 max-w-xl text-[14px] leading-7 text-[color:var(--rd-fg-muted)]">
              Pick a target. The planner runs SLSQP on your trained Ridge with
              physiological bounds (sleep 5–10h, strain 0–21, alcohol 0) and
              returns the closest reachable plan. Coach can't do this.
            </p>
          </div>

          <div className="rd-card mb-8">
            <div className="flex flex-col gap-5">
              <label className="flex flex-col gap-3">
                <div className="flex items-baseline justify-between">
                  <span className="rd-eyebrow">Target recovery</span>
                  <span className="mono text-[24px]">{target}</span>
                </div>
                <input
                  type="range"
                  min={30}
                  max={99}
                  step={1}
                  value={target}
                  onChange={(e) => setTarget(parseInt(e.target.value))}
                  className="w-full accent-[color:var(--rd-accent)]"
                />
              </label>
              <button
                className="rd-btn rd-btn-primary self-start disabled:opacity-50"
                onClick={submit}
                disabled={pending}
              >
                {pending ? "Solving…" : "Solve"}
                <svg
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="M5 12h14M13 6l6 6-6 6" />
                </svg>
              </button>
            </div>
          </div>

          {error ? (
            <p className="rd-card text-[13px] text-[color:var(--rd-withdraw)]">
              {error}
            </p>
          ) : null}

          {resp ? (
            <div className="rd-card flex flex-col gap-6">
              <div className="flex items-baseline justify-between">
                <div>
                  <span className="rd-eyebrow">For {resp.target_day}</span>
                  <div className="mt-2 flex items-baseline gap-3">
                    <span className="rd-stat-num rd-stat-lg">
                      {resp.achieved_recovery.toFixed(1)}
                    </span>
                    <span className="rd-eyebrow">predicted</span>
                  </div>
                </div>
                <span
                  className={
                    "rd-chip mono " +
                    (resp.feasible ? "rd-chip-deposit" : "rd-chip-withdraw")
                  }
                >
                  <span className="rd-chip-dot" />
                  {resp.feasible
                    ? "Target reachable"
                    : `Closest: ${resp.achieved_recovery.toFixed(0)}`}
                </span>
              </div>

              {resp.infeasibility_reason ? (
                <p className="text-[13px] leading-6 text-[color:var(--rd-fg-body)]">
                  {resp.infeasibility_reason}
                </p>
              ) : null}

              <div className="rd-divider" />

              <div className="flex flex-col gap-3">
                <span className="rd-eyebrow">Recommended plan</span>
                {resp.actions.length === 0 ? (
                  <p className="text-[13px] text-[color:var(--rd-fg-muted)]">
                    Stay on your current routine — your baseline already hits
                    this target.
                  </p>
                ) : (
                  resp.actions
                    .map((a) => {
                      const desc = FEATURE_DESC[a.feature]?.(a.value) ?? null;
                      if (!desc) return null;
                      return (
                        <div
                          key={a.feature}
                          className="flex items-center justify-between border-b border-[color:var(--rd-hair-soft)] py-2 last:border-b-0"
                        >
                          <span className="text-[13px] text-[color:var(--rd-fg-body)]">
                            {desc}
                          </span>
                          {a.at_upper_bound || a.at_lower_bound ? (
                            <span className="rd-chip mono">at bound</span>
                          ) : null}
                        </div>
                      );
                    })
                    .filter(Boolean)
                )}
              </div>
            </div>
          ) : null}
        </div>
      </main>
    </div>
  );
}
