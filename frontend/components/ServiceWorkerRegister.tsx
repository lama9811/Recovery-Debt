"use client";

import { useEffect } from "react";

export function ServiceWorkerRegister() {
  useEffect(() => {
    if (typeof window === "undefined") return;
    if (!("serviceWorker" in navigator)) return;
    if (process.env.NODE_ENV !== "production") return;

    navigator.serviceWorker.register("/sw.js", { scope: "/", updateViaCache: "none" }).catch(() => {
      // Registration failures are non-fatal; PWA install still works without push.
    });
  }, []);

  return null;
}
