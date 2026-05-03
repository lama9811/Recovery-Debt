"use client";

import { useEffect, useState } from "react";

import { API_URL, apiGet } from "@/lib/api";

type Status =
  | { kind: "loading" }
  | { kind: "demo" }
  | { kind: "connected"; n: number };

type WhoopStatus = { connected_users: number };

export function ConnectWhoopCTA() {
  const [status, setStatus] = useState<Status>({ kind: "loading" });

  useEffect(() => {
    apiGet<WhoopStatus>("/api/whoop/status")
      .then((r) =>
        setStatus(
          r.connected_users > 0
            ? { kind: "connected", n: r.connected_users }
            : { kind: "demo" },
        ),
      )
      .catch(() => setStatus({ kind: "demo" }));
  }, []);

  if (status.kind === "loading") {
    return (
      <div className="rd-card flex flex-col gap-2">
        <span className="rd-eyebrow">WHOOP</span>
        <span className="text-[12px] text-[color:var(--rd-fg-muted)]">…</span>
      </div>
    );
  }

  if (status.kind === "connected") {
    return (
      <div className="rd-card flex flex-col gap-3">
        <span className="rd-eyebrow">WHOOP</span>
        <div className="flex items-baseline gap-2">
          <span className="rd-stat-num rd-stat-lg">✓</span>
          <span className="text-[12px] text-[color:var(--rd-fg-muted)]">
            connected
          </span>
        </div>
        <p className="text-[11px] leading-5 text-[color:var(--rd-fg-muted)]">
          Backfill runs in the background. Refresh in a minute to see your data.
        </p>
      </div>
    );
  }

  return (
    <div className="rd-card flex flex-col gap-3">
      <span className="rd-eyebrow">WHOOP</span>
      <p className="text-[13px] leading-6 text-[color:var(--rd-fg)]">
        You&apos;re viewing demo data. Connect your WHOOP to see your real
        recovery, sleep, and strain.
      </p>
      <a
        href={`${API_URL}/api/whoop/connect`}
        className="rd-btn rd-btn-primary text-[12px] self-start"
      >
        Connect WHOOP
      </a>
    </div>
  );
}
