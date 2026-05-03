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

### Tier-1 differentiation features (CLAUDE.md §"Tier-1") — all built

- **Inverse Planner** — `POST /api/plan` + `/plan` page
- **Sensitivity Profile** — `GET /api/profile` + `/profile` page
- **Cumulative SHAP Wallet** — `GET /api/wallet` + `/wallet` page

### ⏳ Remaining (all manual, no engineering left)

| Step | Notes |
|---|---|
| Apply `db/migrations/001_push_subscriptions.sql` to live Supabase | Paste into Supabase SQL editor; idempotent |
| Frontend deploy to Vercel | Set `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_VAPID_PUBLIC_KEY` |
| Set `VAPID_PRIVATE_KEY` (PEM content) + `VAPID_SUBJECT` on Railway | Multi-line OK in Railway env |
| Add three Railway cron schedules from `backend/CRONS.md` | One service per cron; Railway disables web command for cron services |
| Register webhook URL in WHOOP dev portal | Once frontend URL is known |
| Stable IQR whiskers from real history (need ≥10 model versions) | UI shows placeholder bands until then |
| Loom walkthrough | After real WHOOP data accumulates |

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
WHOOP OAuth (api/whoop.py) → tokens in Supabase
  ↓
workers/backfill.py + api/webhooks.py + 4 AM workers/safety_net.py
  populate recoveries / cycles / sleeps / workouts
  ↓
daily checkin (POST /api/checkin) writes to checkins
  ↓
nightly retrain (workers/train_now.py, scheduled per backend/CRONS.md)
  ├─ build_feature_matrix → RidgeCV(TimeSeriesSplit) → pickle to ml/artifacts/
  └─ shap.LinearExplainer → per-feature contributions to shap_values
  ↓
FastAPI api/data.py reads predictions + receipts:
  GET /api/dashboard | GET /api/receipt | GET /api/profile | GET /api/wallet
  ↓
inverse planner (POST /api/plan → ml/solve.py) on demand

Independent secondary loop (Web Push):
  browser subscribes via lib/push.ts → POST /api/push/subscribe
  ↓
  9 PM workers/notify_evening.py joins push_subscriptions × predictions,
  fans out via pywebpush, prunes 404/410 dead subscriptions
  ↓
  service worker (public/sw.js) shows the notification, deep-links into "/"
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

- Backend: `https://recovery-debt-production.up.railway.app` (`/health` returns `{"ok":true}`)
- Frontend: not yet deployed
- Database: Supabase Postgres
- Repo: `lama9811/Recovery-Debt`, default branch `main`

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
