"use client";

import { useEffect, useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { ErrorState } from "@/components/ErrorState";
import { Nav } from "@/components/Nav";
import { apiGet } from "@/lib/api";

type WalletPoint = Record<string, number | string> & { day: string };

type WalletResp = {
  series: WalletPoint[];
  totals: Record<string, number>;
  n_days: number;
};

const CATEGORIES = ["Sleep", "Strain", "Alcohol", "Stress", "Lifestyle", "Physiology"] as const;
const COLORS: Record<(typeof CATEGORIES)[number], string> = {
  Sleep: "var(--chart-1)",
  Strain: "var(--chart-2)",
  Alcohol: "var(--rd-withdraw)",
  Stress: "var(--chart-4)",
  Lifestyle: "var(--chart-5)",
  Physiology: "var(--chart-3)",
};

export default function Wallet() {
  const [resp, setResp] = useState<WalletResp | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiGet<WalletResp>("/api/wallet")
      .then(setResp)
      .catch((e) => setError(String(e)));
  }, []);

  if (error) {
    return (
      <div className="flex min-h-screen flex-col">
        <Nav />
        <main className="px-10 pb-24 max-w-3xl">
          <ErrorState title="Wallet unavailable" hint={error} />
        </main>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen flex-col">
      <Nav />
      <main className="flex-1 px-10 pb-24">
        <div className="mx-auto max-w-5xl">
          <div className="mb-8">
            <span className="rd-eyebrow">SHAP Wallet</span>
            <h1 className="rd-h1 text-[40px] mt-3">
              Where your recovery went.
            </h1>
            <p className="mt-3 max-w-xl text-[14px] leading-7 text-[color:var(--rd-fg-muted)]">
              Cumulative SHAP contribution per category, re-explained through
              the current model so historical days stay comparable.
            </p>
          </div>

          {/* Totals */}
          <section className="grid grid-cols-2 gap-4 md:grid-cols-3 mb-8">
            {CATEGORIES.map((cat) => {
              const v = resp?.totals?.[cat] ?? 0;
              return (
                <div key={cat} className="rd-card">
                  <span
                    className="rd-eyebrow"
                    style={{ color: COLORS[cat] }}
                  >
                    {cat}
                  </span>
                  <div
                    className={
                      "rd-stat-num rd-stat-md mt-2 " +
                      (v >= 0 ? "rd-deposit" : "rd-withdraw")
                    }
                  >
                    {v >= 0 ? "+" : ""}
                    {v.toFixed(0)}
                  </div>
                  <span className="text-[11px] text-[color:var(--rd-fg-muted)]">
                    cumulative pts
                  </span>
                </div>
              );
            })}
          </section>

          <div className="rd-card" style={{ height: 380 }}>
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={resp?.series ?? []} margin={{ top: 20, right: 24, left: 0, bottom: 8 }}>
                <CartesianGrid stroke="var(--rd-hair-soft)" vertical={false} />
                <XAxis
                  dataKey="day"
                  tick={{ fontSize: 10, fill: "var(--rd-fg-muted)" }}
                  tickFormatter={(v) =>
                    new Date(String(v)).toLocaleDateString(undefined, {
                      month: "short",
                      day: "numeric",
                    })
                  }
                  minTickGap={32}
                />
                <YAxis tick={{ fontSize: 11, fill: "var(--rd-fg-muted)" }} />
                <Tooltip
                  contentStyle={{
                    background: "var(--rd-surface)",
                    border: "1px solid var(--rd-hair)",
                    fontSize: 12,
                  }}
                  labelFormatter={(v) => new Date(String(v)).toLocaleDateString()}
                />
                {CATEGORIES.map((cat) => (
                  <Area
                    key={cat}
                    type="monotone"
                    dataKey={cat}
                    stroke={COLORS[cat]}
                    fill={COLORS[cat]}
                    fillOpacity={0.18}
                    strokeWidth={1.5}
                    dot={false}
                  />
                ))}
              </AreaChart>
            </ResponsiveContainer>
          </div>

          <p className="mt-8 max-w-2xl text-[12px] leading-relaxed text-[color:var(--rd-fg-muted)]">
            <span className="rd-eyebrow mr-2">Honesty</span>
            &ldquo;Cost&rdquo; and &ldquo;deposit&rdquo; labels describe the model&apos;s prediction, not a
            causal effect on your body.
          </p>
        </div>
      </main>
    </div>
  );
}
