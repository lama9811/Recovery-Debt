// Defensive API URL resolution.
//
// `NEXT_PUBLIC_API_URL` is replaced at build time by Next.js. If Vercel
// has the wrong value (e.g. an env var swap put a VAPID key here), the
// bundle ships with that garbage baked in and every fetch fails. Rather
// than rely on the env var being pristine, we validate it and fall back
// to the known production URL when it doesn't look like a URL. This makes
// the app survive Vercel-side misconfiguration without a redeploy.

const PROD_API_URL = "https://recovery-debt-production.up.railway.app";
const LOCAL_API_URL = "http://localhost:8000";

function resolveApiUrl(): string {
  const raw = process.env.NEXT_PUBLIC_API_URL ?? "";
  if (raw.startsWith("http://") || raw.startsWith("https://")) return raw;
  // Browser context: localhost dev → local backend, anything else → prod.
  if (typeof window !== "undefined") {
    return window.location.hostname === "localhost" ? LOCAL_API_URL : PROD_API_URL;
  }
  // SSR / build-time render: prefer prod so the static HTML is correct.
  return PROD_API_URL;
}

export const API_URL = resolveApiUrl();

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`${path} → ${res.status}`);
  return res.json();
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`${path} → ${res.status}`);
  return res.json();
}
