"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { CheckinCTA } from "@/components/CheckinCTA";
import { ConfidenceLabel } from "@/components/ConfidenceLabel";
import { EnableNotificationsButton } from "@/components/EnableNotificationsButton";
import { ErrorState } from "@/components/ErrorState";
import { Nav } from "@/components/Nav";
import { apiGet } from "@/lib/api";

type Day = {
  day: string;
  recovery: number | null;
  hrv: number | null;
  rhr: number | null;
  strain: number | null;
  sleep_h: number | null;
  alcohol: number;
  stress: number | null;
};

type Dashboard = {
  user_id: string;
  days: Day[];
  rolling_7d_avg: number | null;
  n_days: number;
};

type Receipt = {
  target_day: string;
  predicted_recovery: number;
  base_value: number;
  top_contributors: { feature: string; contribution: number }[];
  n_training_days: number;
  model_version: string;
  early_estimate: boolean;
};

const FEATURE_LABEL: Record<string, string> = {
  sleep_h: "Sleep tonight",
  sleep_h_lag1: "Sleep last night",
  sleep_h_lag2: "Sleep two nights ago",
  sleep_h_roll3: "3-day sleep average",
  sleep_h_roll7: "7-day sleep average",
  efficiency_pct: "Sleep efficiency",
  consistency_pct: "Sleep consistency",
  deep_frac: "Deep sleep share",
  rem_frac: "REM sleep share",
  strain_lag1: "Yesterday's strain",
  strain_lag2: "Strain two days ago",
  strain_roll3: "3-day strain average",
  strain_roll7: "7-day strain average",
  hrv_lag1: "Yesterday's HRV",
  hrv_roll7: "7-day HRV average",
  rhr_lag1: "Yesterday's resting HR",
  alcohol_drinks: "Alcohol today",
  alcohol_lag1: "Alcohol yesterday",
  alcohol_roll7: "7-day alcohol average",
  caffeine_mg: "Caffeine",
  stress_1to10: "Stress",
  late_meal_int: "Late meal",
  ill_int: "Feeling ill",
  traveling_int: "Traveling",
  is_weekend: "Weekend",
  missing_checkin: "Missing check-in",
  missing_sleep: "Missing sleep data",
  missing_strain: "Missing strain data",
};

function fmt(n: number | null | undefined, digits = 0): string {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  return n.toFixed(digits);
}

export default function Home() {
  const [dash, setDash] = useState<Dashboard | null>(null);
  const [receipt, setReceipt] = useState<Receipt | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiGet<Dashboard>("/api/dashboard")
      .then(setDash)
      .catch((e) => setError(String(e)));
    apiGet<Receipt>("/api/receipt")
      .then(setReceipt)
      .catch(() => {
        /* receipt is optional — model may not be trained yet */
      });
  }, []);

  if (error) {
    return (
      <div className="flex min-h-screen flex-col">
        <Nav />
        <main className="px-10 pb-24 max-w-3xl">
          <ErrorState
            title="Backend not reachable"
            hint={`${error}. Make sure the FastAPI server is running on :8000 and run \`python -m synth.generator && python -m workers.train_now\` to seed the demo user.`}
          />
        </main>
      </div>
    );
  }

  const recent = dash?.days?.slice(-30).reverse() ?? [];
  const baseline =
    dash?.days && dash.days.length
      ? dash.days
          .map((d) => d.recovery)
          .filter((r): r is number => r != null)
          .reduce((a, b) => a + b, 0) /
        dash.days.filter((d) => d.recovery != null).length
      : 0;

  return (
    <div className="flex min-h-screen flex-col">
      <Nav />
      <main className="flex-1 px-10 pb-24">
        <div className="mx-auto max-w-5xl">
          {/* Header stat block */}
          <section className="grid grid-cols-1 gap-6 md:grid-cols-3 mb-10">
            <div className="rd-card md:col-span-2">
              <span className="rd-eyebrow">7-day balance</span>
              <div className="mt-3 flex items-baseline gap-4">
                <span className="rd-stat-num rd-stat-xl">
                  {fmt(dash?.rolling_7d_avg ?? null, 1)}
                </span>
                <span className="rd-eyebrow">avg recovery</span>
              </div>
              <p className="mt-3 max-w-md text-[13px] leading-6 text-[color:var(--rd-fg-muted)]">
                Your recovery as a running balance. Every row below is a day —
                the receipt explains the deltas.
              </p>
            </div>
            <div className="rd-card flex flex-col gap-4">
              <div className="flex items-center justify-between">
                <span className="rd-eyebrow">Tomorrow&apos;s forecast</span>
                {receipt ? (
                  <ConfidenceLabel nDays={receipt.n_training_days} />
                ) : null}
              </div>
              <div className="rd-stat-num rd-stat-lg">
                {receipt ? fmt(receipt.predicted_recovery, 1) : "—"}
              </div>
              {receipt ? (
                <div className="flex flex-col gap-1.5">
                  <span className="rd-eyebrow">top drivers</span>
                  {receipt.top_contributors.slice(0, 3).map((c) => (
                    <div key={c.feature} className="flex items-center justify-between text-[12px]">
                      <span className="text-[color:var(--rd-fg-body)]">
                        {FEATURE_LABEL[c.feature] ?? c.feature}
                      </span>
                      <span
                        className={
                          "mono " + (c.contribution >= 0 ? "rd-deposit" : "rd-withdraw")
                        }
                      >
                        {c.contribution >= 0 ? "+" : ""}
                        {c.contribution.toFixed(1)}
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-[color:var(--rd-fg-muted)]">
                  Run <code className="mono">python -m workers.train_now</code> to
                  produce a forecast.
                </p>
              )}
              <Link
                href="/plan"
                className="rd-btn rd-btn-ghost mt-2 self-start"
              >
                Plan a target →
              </Link>
              <EnableNotificationsButton />
            </div>
          </section>

          {/* Daily check-in CTA */}
          <section className="mb-10 grid grid-cols-1 gap-6 md:grid-cols-3">
            <CheckinCTA />
          </section>

          {/* Ledger */}
          <section className="rd-card rd-card-tight">
            <div className="rd-card-head">
              <h3>Daily ledger</h3>
              <span className="rd-eyebrow">last 30 days</span>
            </div>
            <div>
              {recent.map((d) => {
                const delta = d.recovery != null ? d.recovery - baseline : null;
                return (
                  <div
                    key={d.day}
                    className="grid grid-cols-12 items-center gap-3 border-b border-[color:var(--rd-hair-soft)] px-6 py-3 last:border-b-0 hover:bg-[color:var(--rd-elev)]"
                  >
                    <div className="col-span-3 text-[12px] tracking-tight text-[color:var(--rd-fg-muted)]">
                      {new Date(d.day).toLocaleDateString(undefined, {
                        weekday: "short",
                        month: "short",
                        day: "numeric",
                      })}
                    </div>
                    <div className="col-span-2 mono text-[18px] tracking-tight text-[color:var(--rd-fg)]">
                      {fmt(d.recovery)}
                    </div>
                    <div className="col-span-2">
                      {delta == null ? null : (
                        <span
                          className={
                            "mono text-[12px] " +
                            (delta >= 0 ? "rd-deposit" : "rd-withdraw")
                          }
                        >
                          {delta >= 0 ? "+" : ""}
                          {delta.toFixed(1)}
                        </span>
                      )}
                    </div>
                    <div className="col-span-5 flex items-center gap-2 text-[11px] text-[color:var(--rd-fg-muted)]">
                      <span>sleep {fmt(d.sleep_h, 1)}h</span>
                      <span className="rd-whisper">·</span>
                      <span>strain {fmt(d.strain, 1)}</span>
                      {d.alcohol > 0 ? (
                        <>
                          <span className="rd-whisper">·</span>
                          <span className="rd-withdraw">alcohol {d.alcohol}</span>
                        </>
                      ) : null}
                      {d.stress != null ? (
                        <>
                          <span className="rd-whisper">·</span>
                          <span>stress {d.stress}/10</span>
                        </>
                      ) : null}
                    </div>
                  </div>
                );
              })}
              {recent.length === 0 ? (
                <div className="px-6 py-12 text-center text-[13px] text-[color:var(--rd-fg-muted)]">
                  No data yet — run{" "}
                  <code className="mono">python -m synth.generator</code> to seed the demo user.
                </div>
              ) : null}
            </div>
          </section>

          {/* Honesty footer */}
          <section className="mt-10">
            <div className="rd-divider" />
            <p className="max-w-2xl text-[12px] leading-relaxed text-[color:var(--rd-fg-muted)]">
              <span className="rd-eyebrow mr-2">Honesty</span>
              On days you logged alcohol, the model predicted lower recovery.
              That&apos;s the model&apos;s pattern, not a medical claim.
            </p>
          </section>
        </div>
      </main>
    </div>
  );
}
