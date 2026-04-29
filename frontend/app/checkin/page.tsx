"use client";

import { useEffect, useState } from "react";

import { Nav } from "@/components/Nav";
import { apiGet, apiPost } from "@/lib/api";

type CheckinGet = {
  submitted: boolean;
  alcohol_drinks?: number;
  caffeine_mg?: number;
  stress_1to10?: number;
  late_meal?: boolean;
  ill?: boolean;
  traveling?: boolean;
};

export default function Checkin() {
  const [alcohol, setAlcohol] = useState(0);
  const [caffeine, setCaffeine] = useState(180);
  const [stress, setStress] = useState(5);
  const [lateMeal, setLateMeal] = useState(false);
  const [ill, setIll] = useState(false);
  const [traveling, setTraveling] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiGet<CheckinGet>("/api/checkin").then((r) => {
      if (r.submitted) {
        setAlcohol(r.alcohol_drinks ?? 0);
        setCaffeine(r.caffeine_mg ?? 180);
        setStress(r.stress_1to10 ?? 5);
        setLateMeal(!!r.late_meal);
        setIll(!!r.ill);
        setTraveling(!!r.traveling);
        setSubmitted(true);
      }
    }).catch(() => {});
  }, []);

  async function submit() {
    setPending(true);
    setError(null);
    try {
      await apiPost("/api/checkin", {
        alcohol_drinks: alcohol,
        caffeine_mg: caffeine,
        stress_1to10: stress,
        late_meal: lateMeal,
        ill,
        traveling,
      });
      setSubmitted(true);
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
        <div className="mx-auto max-w-2xl">
          <div className="mb-8">
            <span className="rd-eyebrow">Daily Check-in</span>
            <h1 className="rd-h1 text-[40px] mt-3">
              Fifteen seconds, every day.
            </h1>
            <p className="mt-3 max-w-xl text-[14px] leading-7 text-[color:var(--rd-fg-muted)]">
              The model needs your data to learn your specific patterns.
              {submitted ? " Today's check-in is saved — edit and resubmit if anything changed." : ""}
            </p>
          </div>

          <div className="rd-card flex flex-col gap-7">
            <Row label="Alcohol drinks" value={alcohol} suffix="">
              <input
                type="number"
                min={0}
                max={20}
                value={alcohol}
                onChange={(e) => setAlcohol(parseInt(e.target.value || "0"))}
                className="mono w-20 rounded-md border border-[color:var(--rd-hair)] bg-transparent px-3 py-2 text-right text-[16px]"
              />
            </Row>

            <Row label="Caffeine" value={caffeine} suffix="mg">
              <input
                type="number"
                min={0}
                max={1000}
                step={20}
                value={caffeine}
                onChange={(e) => setCaffeine(parseInt(e.target.value || "0"))}
                className="mono w-24 rounded-md border border-[color:var(--rd-hair)] bg-transparent px-3 py-2 text-right text-[16px]"
              />
            </Row>

            <Row label="Stress" value={`${stress} / 10`}>
              <input
                type="range"
                min={1}
                max={10}
                step={1}
                value={stress}
                onChange={(e) => setStress(parseInt(e.target.value))}
                className="w-48 accent-[color:var(--rd-accent)]"
              />
            </Row>

            <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
              <Toggle label="Late meal" value={lateMeal} onChange={setLateMeal} />
              <Toggle label="Feeling ill" value={ill} onChange={setIll} />
              <Toggle label="Traveling" value={traveling} onChange={setTraveling} />
            </div>

            <button
              className="rd-btn rd-btn-primary self-start disabled:opacity-50"
              disabled={pending}
              onClick={submit}
            >
              {pending ? "Saving…" : submitted ? "Update" : "Save"}
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M5 13l4 4L19 7" />
              </svg>
            </button>

            {error ? (
              <p className="text-[12px] text-[color:var(--rd-withdraw)]">{error}</p>
            ) : null}
            {submitted && !error ? (
              <p className="text-[12px] text-[color:var(--rd-deposit)]">
                Saved.
              </p>
            ) : null}
          </div>
        </div>
      </main>
    </div>
  );
}

function Row({
  label,
  value,
  suffix,
  children,
}: {
  label: string;
  value: number | string;
  suffix?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex items-center justify-between gap-4">
      <div className="flex flex-col gap-1">
        <span className="rd-eyebrow">{label}</span>
        <span className="mono text-[16px]">
          {value}
          {suffix ? <span className="ml-1 text-[12px] text-[color:var(--rd-fg-muted)]">{suffix}</span> : null}
        </span>
      </div>
      {children}
    </div>
  );
}

function Toggle({
  label,
  value,
  onChange,
}: {
  label: string;
  value: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <label
      className={
        "flex cursor-pointer items-center justify-between rounded-md border px-3 py-3 text-[13px] transition-colors " +
        (value
          ? "border-[color:var(--rd-accent)] bg-[color:var(--rd-accent-soft)] text-[color:var(--rd-fg)]"
          : "border-[color:var(--rd-hair)] text-[color:var(--rd-fg-muted)] hover:bg-[color:var(--rd-elev)]")
      }
    >
      <span>{label}</span>
      <input
        type="checkbox"
        className="sr-only"
        checked={value}
        onChange={(e) => onChange(e.target.checked)}
      />
      <span className="mono text-[11px]">{value ? "yes" : "no"}</span>
    </label>
  );
}
