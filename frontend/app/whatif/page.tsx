"use client";

import { useEffect, useState } from "react";

import { Nav } from "@/components/Nav";
import { apiPost } from "@/lib/api";

type WhatIfResp = {
  predicted_recovery: number;
  baseline_recovery: number;
  delta: number;
};

function Slider({
  label,
  value,
  min,
  max,
  step,
  unit,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  unit?: string;
  onChange: (v: number) => void;
}) {
  return (
    <label className="flex flex-col gap-3">
      <div className="flex items-baseline justify-between">
        <span className="rd-eyebrow">{label}</span>
        <span className="mono text-[18px] text-[color:var(--rd-fg)]">
          {value}
          {unit ? <span className="ml-1 text-[12px] text-[color:var(--rd-fg-muted)]">{unit}</span> : null}
        </span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        className="w-full accent-[color:var(--rd-accent)]"
      />
      <div className="flex justify-between text-[10px] text-[color:var(--rd-fg-whisper)] tracking-wider">
        <span>
          {min}
          {unit}
        </span>
        <span>
          {max}
          {unit}
        </span>
      </div>
    </label>
  );
}

export default function WhatIf() {
  const [sleep, setSleep] = useState(7.5);
  const [strain, setStrain] = useState(11);
  const [alcohol, setAlcohol] = useState(0);
  const [stress, setStress] = useState(5);
  const [resp, setResp] = useState<WhatIfResp | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    apiPost<WhatIfResp>("/api/whatif", {
      sleep_h: sleep,
      strain: strain,
      alcohol_drinks: Math.round(alcohol),
      stress_1to10: Math.round(stress),
    })
      .then((r) => !cancelled && setResp(r))
      .catch((e) => !cancelled && setError(String(e)));
    return () => {
      cancelled = true;
    };
  }, [sleep, strain, alcohol, stress]);

  return (
    <div className="flex min-h-screen flex-col">
      <Nav />
      <main className="flex-1 px-10 pb-24">
        <div className="mx-auto max-w-4xl">
          <div className="mb-10">
            <span className="rd-eyebrow">What-If</span>
            <h1 className="rd-h1 text-[40px] mt-3">If tomorrow looked like…</h1>
            <p className="mt-3 max-w-xl text-[14px] leading-7 text-[color:var(--rd-fg-muted)]">
              Drag the sliders. The forecast updates live, replayed through your
              model. This is a counterfactual on your trained Ridge — not a
              recommendation.
            </p>
          </div>

          <div className="grid grid-cols-1 gap-8 md:grid-cols-2">
            <div className="rd-card flex flex-col gap-7">
              <Slider
                label="Sleep tonight"
                value={sleep}
                min={4}
                max={11}
                step={0.25}
                unit="h"
                onChange={setSleep}
              />
              <Slider
                label="Today's strain"
                value={strain}
                min={0}
                max={21}
                step={0.5}
                onChange={setStrain}
              />
              <Slider
                label="Alcohol drinks"
                value={alcohol}
                min={0}
                max={6}
                step={1}
                onChange={setAlcohol}
              />
              <Slider
                label="Stress"
                value={stress}
                min={1}
                max={10}
                step={1}
                unit="/10"
                onChange={setStress}
              />
            </div>

            <div className="rd-card flex flex-col gap-5">
              <span className="rd-eyebrow">Forecast</span>
              <div className="flex items-baseline gap-3">
                <span className="rd-stat-num rd-stat-xl">
                  {resp ? resp.predicted_recovery.toFixed(1) : "—"}
                </span>
                {resp ? (
                  <span
                    className={
                      "mono text-[14px] " +
                      (resp.delta >= 0 ? "rd-deposit" : "rd-withdraw")
                    }
                  >
                    {resp.delta >= 0 ? "+" : ""}
                    {resp.delta.toFixed(1)} vs baseline
                  </span>
                ) : null}
              </div>
              <div className="rd-divider" />
              <p className="text-[12px] leading-6 text-[color:var(--rd-fg-muted)]">
                Baseline = your last recorded day, replayed through the current
                model. Days with longer sleep had higher predicted recovery in
                your data.
              </p>
              {error ? (
                <p className="text-[12px] text-[color:var(--rd-withdraw)]">
                  {error}
                </p>
              ) : null}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
