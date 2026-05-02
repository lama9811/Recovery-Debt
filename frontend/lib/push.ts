"use client";

import { apiPost } from "@/lib/api";

const VAPID_PUBLIC_KEY = process.env.NEXT_PUBLIC_VAPID_PUBLIC_KEY ?? "";

export type PushSupport =
  | { supported: false; reason: string }
  | { supported: true; permission: NotificationPermission };

export function detectSupport(): PushSupport {
  if (typeof window === "undefined") {
    return { supported: false, reason: "ssr" };
  }
  if (!("serviceWorker" in navigator)) {
    return { supported: false, reason: "no-sw" };
  }
  if (!("PushManager" in window)) {
    return { supported: false, reason: "no-push" };
  }
  if (!VAPID_PUBLIC_KEY) {
    return { supported: false, reason: "no-vapid-key" };
  }
  return { supported: true, permission: Notification.permission };
}

function urlBase64ToUint8Array(base64: string): Uint8Array<ArrayBuffer> {
  const padding = "=".repeat((4 - (base64.length % 4)) % 4);
  const b64 = (base64 + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(b64);
  const buf = new ArrayBuffer(raw.length);
  const out = new Uint8Array(buf);
  for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
  return out;
}

export async function enablePush(): Promise<
  { ok: true } | { ok: false; reason: string }
> {
  const support = detectSupport();
  if (!support.supported) return { ok: false, reason: support.reason };

  const permission = await Notification.requestPermission();
  if (permission !== "granted") return { ok: false, reason: "denied" };

  const reg = await navigator.serviceWorker.ready;
  const existing = await reg.pushManager.getSubscription();
  const sub =
    existing ??
    (await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(VAPID_PUBLIC_KEY),
    }));

  const json = sub.toJSON() as {
    endpoint?: string;
    keys?: { p256dh?: string; auth?: string };
  };
  if (!json.endpoint || !json.keys?.p256dh || !json.keys?.auth) {
    return { ok: false, reason: "bad-subscription" };
  }

  await apiPost("/api/push/subscribe", {
    endpoint: json.endpoint,
    p256dh: json.keys.p256dh,
    auth: json.keys.auth,
  });
  return { ok: true };
}
