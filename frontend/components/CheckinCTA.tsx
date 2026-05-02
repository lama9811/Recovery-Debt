"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { apiGet } from "@/lib/api";

type CheckinStatus =
  | { kind: "loading" }
  | { kind: "submitted" }
  | { kind: "missing" }
  | { kind: "error" };

type CheckinResponse = { submitted: boolean };

export function CheckinCTA() {
  const [status, setStatus] = useState<CheckinStatus>({ kind: "loading" });

  useEffect(() => {
    apiGet<CheckinResponse>("/api/checkin")
      .then((r) =>
        setStatus(r.submitted ? { kind: "submitted" } : { kind: "missing" }),
      )
      .catch(() => setStatus({ kind: "error" }));
  }, []);

  if (status.kind === "loading") {
    return (
      <div className="rd-card flex flex-col gap-2">
        <span className="rd-eyebrow">Today&apos;s check-in</span>
        <span className="text-[12px] text-[color:var(--rd-fg-muted)]">…</span>
      </div>
    );
  }

  if (status.kind === "submitted") {
    return (
      <div className="rd-card flex flex-col gap-3">
        <span className="rd-eyebrow">Today&apos;s check-in</span>
        <div className="flex items-baseline gap-2">
          <span className="rd-stat-num rd-stat-lg">✓</span>
          <span className="text-[12px] text-[color:var(--rd-fg-muted)]">
            logged
          </span>
        </div>
        <Link href="/checkin" className="rd-btn rd-btn-ghost text-[12px] self-start">
          Edit →
        </Link>
      </div>
    );
  }

  return (
    <div className="rd-card flex flex-col gap-3">
      <span className="rd-eyebrow">Today&apos;s check-in</span>
      <p className="text-[13px] leading-6 text-[color:var(--rd-fg)]">
        15 seconds. Alcohol, stress, late meal, sick, traveling.
      </p>
      <Link href="/checkin" className="rd-btn rd-btn-primary text-[12px] self-start">
        Log today&apos;s check-in
      </Link>
    </div>
  );
}
