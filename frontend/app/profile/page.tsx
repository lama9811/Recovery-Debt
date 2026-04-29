"use client";

import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ErrorBar,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { ErrorState } from "@/components/ErrorState";
import { Nav } from "@/components/Nav";
import { apiGet } from "@/lib/api";

type ProfileFeature = {
  name: string;
  coef_per_unit: number;
  median_per_unit: number;
  iqr_lo: number;
  iqr_hi: number;
  stable: boolean;
};

type ProfileResp = {
  n_model_versions: number;
  features: ProfileFeature[];
};

const FEATURE_LABEL: Record<string, string> = {
  sleep_h: "Sleep tonight",
  sleep_h_lag1: "Sleep last night",
  sleep_h_roll7: "7d sleep avg",
  strain_lag1: "Yesterday strain",
  strain_roll7: "7d strain avg",
  hrv_lag1: "Yesterday HRV",
  hrv_roll7: "7d HRV avg",
  rhr_lag1: "Yesterday RHR",
  alcohol_drinks: "Alcohol",
  alcohol_lag1: "Alcohol yest.",
  stress_1to10: "Stress",
  caffeine_mg: "Caffeine",
  late_meal_int: "Late meal",
  ill_int: "Illness",
  traveling_int: "Travel",
  is_weekend: "Weekend",
};

export default function Profile() {
  const [resp, setResp] = useState<ProfileResp | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiGet<ProfileResp>("/api/profile")
      .then(setResp)
      .catch((e) => setError(String(e)));
  }, []);

  if (error) {
    return (
      <div className="flex min-h-screen flex-col">
        <Nav />
        <main className="px-10 pb-24 max-w-3xl">
          <ErrorState title="Profile unavailable" hint={error} />
        </main>
      </div>
    );
  }

  // Top-12 features by absolute coefficient — drops the missingness flags
  // and the noisy ones, keeps the recruiter-readable signal.
  const topFeatures = [...(resp?.features ?? [])]
    .filter((f) => FEATURE_LABEL[f.name])
    .sort((a, b) => Math.abs(b.coef_per_unit) - Math.abs(a.coef_per_unit))
    .slice(0, 12)
    .map((f) => ({
      name: FEATURE_LABEL[f.name] ?? f.name,
      coef: f.coef_per_unit,
      iqr: [f.iqr_lo, f.iqr_hi] as [number, number],
      iqrError: [
        Math.abs(f.coef_per_unit - f.iqr_lo),
        Math.abs(f.iqr_hi - f.coef_per_unit),
      ],
    }));

  return (
    <div className="flex min-h-screen flex-col">
      <Nav />
      <main className="flex-1 px-10 pb-24">
        <div className="mx-auto max-w-5xl">
          <div className="mb-8">
            <span className="rd-eyebrow">Sensitivity Profile</span>
            <h1 className="rd-h1 text-[40px] mt-3">
              How your body responds, per unit.
            </h1>
            <p className="mt-3 max-w-xl text-[14px] leading-7 text-[color:var(--rd-fg-muted)]">
              Each bar is a Ridge coefficient in the model's natural units —
              points of recovery per hour of sleep, per drink, per strain unit.
              Whiskers show the IQR across recent retrains.
            </p>
          </div>

          <div className="rd-card" style={{ height: 460 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={topFeatures}
                margin={{ top: 20, right: 24, bottom: 40, left: 0 }}
                barCategoryGap={12}
              >
                <CartesianGrid stroke="var(--rd-hair-soft)" vertical={false} />
                <XAxis
                  dataKey="name"
                  tick={{ fontSize: 11, fill: "var(--rd-fg-muted)" }}
                  interval={0}
                  angle={-25}
                  textAnchor="end"
                  height={70}
                />
                <YAxis
                  tick={{ fontSize: 11, fill: "var(--rd-fg-muted)" }}
                  label={{
                    value: "pts of recovery / unit",
                    angle: -90,
                    position: "insideLeft",
                    fill: "var(--rd-fg-muted)",
                    fontSize: 11,
                  }}
                />
                <Tooltip
                  cursor={{ fill: "var(--rd-elev)" }}
                  contentStyle={{
                    background: "var(--rd-surface)",
                    border: "1px solid var(--rd-hair)",
                    fontSize: 12,
                  }}
                  formatter={(v: number) => [v.toFixed(2), "coef"]}
                />
                <Bar dataKey="coef" radius={[4, 4, 0, 0]}>
                  <ErrorBar
                    dataKey="iqrError"
                    width={4}
                    strokeWidth={1.2}
                    stroke="var(--rd-fg-muted)"
                  />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          <p className="mt-8 max-w-2xl text-[12px] leading-relaxed text-[color:var(--rd-fg-muted)]">
            <span className="rd-eyebrow mr-2">Honesty</span>
            Trained on {resp?.n_model_versions ?? 0} model version
            {resp?.n_model_versions === 1 ? "" : "s"}. With limited training
            data the IQR is a placeholder until ≥10 retrains are available.
          </p>
        </div>
      </main>
    </div>
  );
}
