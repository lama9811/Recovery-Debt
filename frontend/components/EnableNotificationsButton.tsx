"use client";

import { useState, useSyncExternalStore } from "react";

import { detectSupport, enablePush } from "@/lib/push";

type BaseStatus =
  | { kind: "loading" }
  | { kind: "unsupported"; reason: string }
  | { kind: "idle" }
  | { kind: "granted" }
  | { kind: "denied" };

type Override =
  | { kind: "granted" }
  | { kind: "denied" }
  | { kind: "error"; reason: string };

type Status = BaseStatus | Override;

const noopSubscribe = () => () => {};

function getBrowserSnapshot(): BaseStatus {
  const s = detectSupport();
  if (!s.supported) return { kind: "unsupported", reason: s.reason };
  if (s.permission === "granted") return { kind: "granted" };
  if (s.permission === "denied") return { kind: "denied" };
  return { kind: "idle" };
}

const getServerSnapshot = (): BaseStatus => ({ kind: "loading" });

export function EnableNotificationsButton() {
  const base = useSyncExternalStore(
    noopSubscribe,
    getBrowserSnapshot,
    getServerSnapshot,
  );
  const [override, setOverride] = useState<Override | null>(null);
  const status: Status = override ?? base;

  if (status.kind === "loading" || status.kind === "unsupported") return null;

  if (status.kind === "granted") {
    return (
      <span className="text-[12px] text-[color:var(--rd-fg-muted)]">
        Evening forecast notifications: on
      </span>
    );
  }

  if (status.kind === "denied") {
    return (
      <span className="text-[12px] text-[color:var(--rd-fg-muted)]">
        Notifications blocked in your browser settings.
      </span>
    );
  }

  return (
    <button
      type="button"
      className="rd-btn rd-btn-ghost text-[12px] self-start"
      onClick={async () => {
        const res = await enablePush();
        if (res.ok) {
          setOverride({ kind: "granted" });
        } else if (res.reason === "denied") {
          setOverride({ kind: "denied" });
        } else {
          setOverride({ kind: "error", reason: res.reason });
        }
      }}
    >
      {status.kind === "error"
        ? `Couldn't enable (${status.reason}). Try again`
        : "Get a 9 PM forecast notification"}
    </button>
  );
}
