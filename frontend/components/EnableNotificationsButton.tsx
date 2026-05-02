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

// useSyncExternalStore requires snapshots to be reference-stable across calls
// for the same logical state — otherwise React detects a change every render
// and warns "should be cached to avoid an infinite loop". So we keep one
// frozen object per possible state and return it.
const STATUS_LOADING: BaseStatus = { kind: "loading" };
const STATUS_IDLE: BaseStatus = { kind: "idle" };
const STATUS_GRANTED: BaseStatus = { kind: "granted" };
const STATUS_DENIED: BaseStatus = { kind: "denied" };

let unsupportedCache: { reason: string; status: BaseStatus } | null = null;
function unsupportedSnapshot(reason: string): BaseStatus {
  if (unsupportedCache?.reason !== reason) {
    unsupportedCache = { reason, status: { kind: "unsupported", reason } };
  }
  return unsupportedCache.status;
}

function getBrowserSnapshot(): BaseStatus {
  const s = detectSupport();
  if (!s.supported) return unsupportedSnapshot(s.reason);
  if (s.permission === "granted") return STATUS_GRANTED;
  if (s.permission === "denied") return STATUS_DENIED;
  return STATUS_IDLE;
}

const getServerSnapshot = (): BaseStatus => STATUS_LOADING;

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
