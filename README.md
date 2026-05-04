# Recovery Debt

A personal PWA that connects to your WHOOP, trains a per-user Ridge regression
on your data, and presents the recovery score as a bank-statement-style ledger
with SHAP receipts, a what-if simulator, and an inverse planner that solves for
the behaviors required to hit a recovery target.

Source-of-truth design docs: `Recovery_Debt_PRD.md`, `OVERVIEW.md`, `PLAN.md`,
`BUILD_GUIDE.md`. The PRD wins when there's ambiguity.

## Quick demo (no WHOOP needed)

```bash
# Backend — seed synthetic data and train the model
cd backend
.venv/bin/pip install -r requirements-full.txt
cp .env.example .env   # fill in DATABASE_URL (Supabase) at minimum
.venv/bin/python -m synth.generator       # 180 days of correlated demo data
.venv/bin/python -m workers.train_now     # train Ridge + SHAP, predict tomorrow
.venv/bin/uvicorn api.main:app --reload   # http://localhost:8000

# Frontend
cd ../frontend
npm ci
npm run dev                                # http://localhost:3000
```

Then open http://localhost:3000 and click around: the **ledger** (home) shows
the synthetic recovery history with deltas, **What-If** lets you drag sliders
and see the prediction update live, and **Plan** runs the inverse planner —
type a target recovery and get back either a feasible plan or "closest
reachable is X because Y is at its physiological bound."

## Repo layout

- `frontend/` — Next.js 16 + React 19 + Tailwind v4 + shadcn (Lamarca design
  system). Deploys to Vercel.
- `backend/` — FastAPI app (`api/`), ML pipeline (`ml/`), background workers
  (`workers/`), DB schema (`db/`), synthetic-data generator (`synth/`),
  tests (`tests/`). Deploys to Railway.

## Status

### ✅ Built

| Day | Feature | Where |
|---|---|---|
| 1 | Next.js + FastAPI skeletons | `frontend/`, `backend/api/main.py` |
| 2 | WHOOP OAuth, 11-table DB schema, Lamarca design system | `backend/api/whoop.py`, `backend/db/schema.sql`, `frontend/app/page.tsx` |
| 6 | Daily check-in (POST/GET, idempotent on `(user_id, day)`) | `backend/api/checkin.py`, `frontend/app/checkin/page.tsx` |
| 7 | **Pure** `build_feature_matrix` (28 features, lagged + rolling + missingness flags) | `backend/ml/features.py` |
| 8 | Ridge + `TimeSeriesSplit` (no random splits — leak guard asserts `val_idx > train_idx.max()`) | `backend/ml/train.py` |
| 9 | `shap.LinearExplainer` fit on the post-scaler representation; integrity test asserts `\|base + Σ contrib − pred\| < 0.01` | `backend/ml/explain.py`, `backend/tests/test_shap_integrity.py` |
| 10 | Manual end-to-end retrain CLI (predict tomorrow, persist SHAP) | `backend/workers/train_now.py` |
| 11 | Bank-statement ledger UI (rolling 7-day balance, top-3 SHAP per day, tomorrow's forecast card) | `frontend/app/page.tsx` |
| 12 | What-If simulator (4 sliders → live counterfactual replay through current model) | `frontend/app/whatif/page.tsx`, `POST /api/whatif` |
| 13 | **Inverse Planner** — SLSQP on Ridge coefficients with hard physiological bounds (sleep 5–10h, strain 0–21, alcohol = 0). Surfaces "closest reachable + which bound pinned us" when infeasible. | `backend/ml/solve.py`, `frontend/app/plan/page.tsx`, `POST /api/plan` |
| 14 | Sensitivity Profile (per-unit Ridge coefficients, IQR whiskers) + Cumulative SHAP Wallet (per-category area chart, re-explained through current model) | `frontend/app/profile/page.tsx`, `frontend/app/wallet/page.tsx` |
| 15 | **Demo mode** — synthetic 180-day correlated dataset, idempotent | `backend/synth/generator.py` |
| 3 | **WHOOP backfill** — token refresh + paged pull of recovery/cycle/sleep/workout, idempotent upserts, rate-limit aware | `backend/workers/backfill.py` |
| 4 | **WHOOP webhooks** — HMAC-SHA256 verified, async re-pull of last 3 days | `backend/api/webhooks.py` |
| 4 | **Safety-net cron** — re-pull last 3 days for every connected user | `backend/workers/safety_net.py` |
| 10 | **Nightly retrain cron config** — Railway dashboard schedule for `train_now.py` | `backend/CRONS.md` |
| 15 | **PWA install** — manifest.ts, SVG icons, iOS-friendly viewport, service worker | `frontend/app/manifest.ts`, `frontend/public/sw.js`, `frontend/components/ServiceWorkerRegister.tsx` |
| 15 | **Web Push pipeline** — `push_subscriptions` table + migration, subscribe/unsubscribe API, `EnableNotificationsButton`, 9 PM `notify_evening` worker that prunes 404/410 dead subs and honors PRD §13 "early estimate" labeling. Worker accepts VAPID private key as either inline PEM or file path. | `backend/api/push.py`, `backend/workers/notify_evening.py`, `backend/db/migrations/001_push_subscriptions.sql`, `frontend/lib/push.ts`, `frontend/components/EnableNotificationsButton.tsx` |
| 15 | **Daily check-in CTA** on the dashboard — fetches `/api/checkin` and surfaces "Log today's check-in" or "Logged ✓" so the daily action isn't buried in the nav | `frontend/components/CheckinCTA.tsx` |
| 15 | **VAPID keypair generator** — P-256 ECDSA via `cryptography`, no extra dep beyond what we already had | `backend/scripts/generate_vapid.py` |
| 15 | **Real-WHOOP mode** — `Connect WHOOP` button on the dashboard, dynamic `resolve_active_user_id()` (real user when present, demo fallback), auto-backfill scheduled as a `BackgroundTask` in the OAuth callback. Manual `POST /api/whoop/backfill` and `/backfill-sync` (debug, returns the actual traceback) endpoints as safety nets when the BackgroundTask doesn't fire. | `frontend/components/ConnectWhoopCTA.tsx`, `backend/api/whoop.py`, `backend/db/client.py` |
| 15 | **`/health/db` deep health check** — proves the pool opened and `SELECT 1` works. Bisects "app booted but DB is dead" issues with one curl. | `backend/api/main.py` |
| 15 | **Self-healing API URL on the frontend** — `frontend/lib/api.ts` validates `NEXT_PUBLIC_API_URL` is a real URL; falls back to a hardcoded prod Railway URL when the env var is misset (e.g. swapped with the VAPID key). Localhost dev still hits `:8000`. | `frontend/lib/api.ts` |
| 15 | **Production hardening** — pgbouncer-compatible asyncpg (`statement_cache_size=0`); `backfill_user(pool, ...)` releases connection between paged WHOOP calls so Supabase's pooler can't time it out; loud `print()` traceback on lifespan/backfill failures so Railway logs surface them; `secure=True` cookies on HTTPS redirects; `BackgroundTasks` (not `asyncio.create_task`) for webhook re-pulls so the GC doesn't collect mid-run. | `backend/db/client.py`, `backend/workers/backfill.py`, `backend/api/main.py`, `backend/api/whoop.py`, `backend/api/webhooks.py` |
| 15 | **Friendly empty states** — `ErrorState` detects `→ 503` and renders "Your model isn't ready yet" instead of a raw error. New users hitting `/plan`, `/profile`, `/wallet`, `/whatif` before the first nightly retrain get an explanation, not a stack trace. | `frontend/components/ErrorState.tsx` |

### Tier-1 differentiation features (CLAUDE.md §"Tier-1") — all built

- **Inverse Planner** — `POST /api/plan` + `/plan` page
- **Sensitivity Profile** — `GET /api/profile` + `/profile` page
- **Cumulative SHAP Wallet** — `GET /api/wallet` + `/wallet` page

### ⏳ Remaining

| Step | Notes |
|---|---|
| Stable IQR whiskers from real history (need ≥10 model versions) | UI shows placeholder bands until then |
| Loom walkthrough | After ~30 days of real WHOOP data accumulates |

### 🔒 Load-bearing invariants (CLAUDE.md — guarded by tests)

1. `build_feature_matrix` is pure → `tests/test_features.py::test_pure`
2. `TimeSeriesSplit` only, no random splits → `test_no_future_leakage`
3. SHAP integrity within 0.01 → `test_shap_integrity.py`
4. Inverse planner respects physiological bounds → `test_solve.py`
5. Push payload honors PRD §13 honesty (early-estimate label, no imperatives) → `test_notify_evening.py`

## Run locally

```bash
# 1. Backend
cd backend
python -m venv .venv
.venv/bin/pip install -r requirements-full.txt
cp .env.example .env  # fill in DATABASE_URL etc.
.venv/bin/python -m synth.generator        # seed 180 days of demo data
.venv/bin/python -m workers.train_now      # train Ridge + SHAP, persist artifact
.venv/bin/uvicorn api.main:app --reload --port 8000

# 2. Frontend (separate terminal)
cd frontend
npm ci
npm run dev   # http://localhost:3000
```

### Pre-commit gate

```bash
cd backend  && ruff check . && pytest -x
cd frontend && npm run lint && npm run build
```

Current state on `feat/days-6-15-ml-pipeline-and-ui`: ✅ ruff clean ·
✅ 12/12 pytest pass · ✅ eslint clean · ✅ `next build` produces 8 static
routes including `/manifest.webmanifest`.

## Architecture (one-request lifecycle)

```
User clicks "Connect WHOOP" on Vercel → /api/whoop/connect (Railway)
  ↓ OAuth state cookie (secure=True on HTTPS)
WHOOP login → /api/whoop/callback?code&state
  ↓ exchange code → upsert users + whoop_tokens
  ├─ schedule _backfill_after_connect as a FastAPI BackgroundTask
  │     (uses Pool.acquire() per endpoint so pgbouncer can't kill the connection)
  └─ RedirectResponse → ${FRONTEND_URL}/?connected=1

4 AM workers/safety_net.py + WHOOP webhooks → re-pull last 3 days for every user
  ↓
4:30 AM workers/train_now.py
  ├─ build_feature_matrix → RidgeCV(TimeSeriesSplit) → pickle to ml/artifacts/
  └─ shap.LinearExplainer → per-feature contributions to shap_values

User submits daily checkin (POST /api/checkin) → checkins table

FastAPI api/data.py reads predictions + receipts via resolve_active_user_id()
  (prefers real-WHOOP user, falls back to demo):
  GET /api/dashboard | /api/receipt | /api/profile | /api/wallet
  POST /api/whatif (slider replay) | /api/plan (SLSQP inverse planner)

Independent secondary loop (Web Push):
  browser subscribes via lib/push.ts → POST /api/push/subscribe
  ↓
  9 PM workers/notify_evening.py joins push_subscriptions × predictions,
  fans out via pywebpush, prunes 404/410 dead subscriptions
  ↓
  service worker (public/sw.js) shows the notification, deep-links into "/"

Diagnostic endpoints when prod misbehaves:
  /health        → app boot
  /health/db     → pool opened + SELECT 1
  /api/whoop/status      → connected_users count
  POST /api/whoop/backfill       → schedule manual backfill
  POST /api/whoop/backfill-sync  → run synchronously, return traceback in JSON
```

## Honesty rules (PRD §13 — enforced in UI copy)

- ❌ "Alcohol costs you 11 points." → ✅ "On days you logged alcohol, your model predicted 11 points lower."
- ❌ "You should sleep more." → ✅ "Days with longer sleep had higher predicted recovery."
- ❌ Any medical claim. Ever.
- Before day 60 of training data, every insight is labeled "early estimate" — see `frontend/components/ConfidenceLabel.tsx`.

## Environment

`backend/.env.example` lists the required vars; `frontend/.env.local.example`
lists the frontend ones. Never commit a populated `.env*` (gitignored). For
deploy, Railway / Vercel inject env vars directly.

For Web Push, generate a VAPID keypair once with
`cd backend && .venv/bin/python -m scripts.generate_vapid`. The script writes
`vapid_private.pem` (gitignored) and `vapid_public.txt` (gitignored). The
private key path goes in `VAPID_PRIVATE_KEY` (or paste the PEM contents in
prod); the public key string goes in `NEXT_PUBLIC_VAPID_PUBLIC_KEY`.

## Production

- Backend: `https://recovery-debt-production.up.railway.app`
- Frontend: deployed on Vercel (auto-deploys on push to `main`)
- Database: Supabase Postgres (Transaction Pooler URL, port 6543, IPv4)
- Crons: 4 services on Railway — `Recovery-Debt` (web), `cron-safety-net`, `cron-train-now`, `cron-notify-evening`
- Repo: `lama9811/Recovery-Debt`, default branch `main`

### Production deployment gotchas (learned the hard way — see CLAUDE.md "Production deployment gotchas" for full detail)

1. **`DATABASE_URL` must be Supabase's IPv4 Transaction Pooler URL** (`*.pooler.supabase.com:6543`), not the direct host. Direct host is IPv6-only; Railway can't reach it. URL-encode special chars in the password (`@`→`%40`, `$`→`%24`).
2. **`backend/requirements.txt` must include the full ML stack.** A slim Day-2 version causes import failures on the data routes; Railway papers over by serving the previous build.
3. **`NEXT_PUBLIC_*` env vars are baked at build time** — redeploy without build cache after editing them on Vercel.
4. **Railway crons are separate services per cron**, sharing variables via `${{Recovery-Debt.NAME}}` references. Don't put cron schedules on the web service.
5. **WHOOP redirect URI** is the backend callback — register `https://<railway>/api/whoop/callback`, not the Vercel URL.
6. **Apply `db/migrations/001_push_subscriptions.sql`** to live Supabase before scheduling the 9 PM `notify_evening` cron.
7. **Generate VAPID keypair** with `cd backend && .venv/bin/python -m scripts.generate_vapid` — public key → Vercel `NEXT_PUBLIC_VAPID_PUBLIC_KEY`, private key (PEM contents) → Railway `VAPID_PRIVATE_KEY`. Plus `VAPID_SUBJECT=mailto:you@example.com` on Railway.

## Notes

- The PWA service worker (`frontend/public/sw.js`) only registers when
  `NODE_ENV === "production"` — to install the app on a phone home
  screen locally, run `npm run build && npm run start` rather than
  `npm run dev`.
- `frontend/next.config.ts` sets `nosniff`, `Referrer-Policy`, and
  `Cache-Control: no-cache` on `/sw.js` so updates ship instantly.
- The `:8000` and `:3000` dev servers can persist between sessions; if
  `next dev` reports "Port 3000 is in use", `lsof -i :3000` then
  `kill <PID>` clears the squatter.
