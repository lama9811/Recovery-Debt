# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Recovery Debt is a personal PWA that connects to the user's WHOOP, trains a per-user Ridge regression model on their data, and presents the recovery score as a bank-statement-style ledger with SHAP receipts, a what-if simulator, and an inverse planner that solves for the behaviors required to hit a recovery target. Source-of-truth design docs:

- `Recovery_Debt_PRD.md` — full spec; the contract for all design decisions.
- `OVERVIEW.md` — strategic summary and feature map.
- `PLAN.md` — day-by-day build checklist.
- `BUILD_GUIDE.md` — full technical build doc with code skeletons, env vars, and the canonical project layout (`§3 Project Structure`, `§4 Environment Variables`).

When a design decision is unclear, the PRD wins.

## Repo layout

Two top-level apps that deploy independently:

- `frontend/` — Next.js 16.2.4 + React 19 + Tailwind v4 + shadcn (`base-nova` style, neutral base, lucide icons). Deploys to Vercel.
- `backend/` — FastAPI app (`api/`), ML pipeline (`ml/`), background workers (`workers/`), DB schema/seeds (`db/`), synthetic-data generator (`synth/`), tests (`tests/`). Deploys to Railway.

Path aliases in `frontend/components.json`: `@/components`, `@/components/ui`, `@/lib`, `@/lib/utils`, `@/hooks`.

### Where the load-bearing code lives

- `backend/ml/features.py` — pure `build_feature_matrix` (28 features, lagged + rolling + missingness flags). Single source of truth for `FEATURE_COLUMNS`.
- `backend/ml/train.py` — `RidgeCV` + `TimeSeriesSplit`; `latest_artifact()` is the canonical loader.
- `backend/ml/explain.py` — `make_explainer(pipeline, X_train)` and `explain_one(...)`. Always pass the *raw* `X_train`; the function applies `pipeline[:-1].transform` internally.
- `backend/ml/solve.py` — `solve_for_target(pipeline, recent_features, target)` returns a `SolveResult` with `feasible`, `achieved_recovery`, `actions`, `infeasibility_reason`. Bounds live in `PHYSIOLOGICAL_BOUNDS`.
- `backend/synth/generator.py` — 180-day demo dataset for `demo@recoverydebt.local`. Idempotent.
- `backend/workers/backfill.py` — real-WHOOP 6-month pull with refresh-token grant. `backfill_user(pool_or_conn, user_id, days)` accepts either a `Pool` (preferred — releases connection between paged endpoint calls so Supabase's transaction-mode pgbouncer can't time out a long-held connection) or a `Connection` (legacy CLI). All four call sites use the Pool form.
- `backend/workers/safety_net.py` — re-pull last 3 days for every user. 4 AM cron. Uses an asyncpg `Pool` (not a single Connection) so the pgbouncer pooler can't kill an idle connection between WHOOP API calls.
- `backend/workers/train_now.py` — end-to-end retrain CLI (Day 10 cron entry point).
- `backend/workers/notify_evening.py` — 9 PM Web Push: tomorrow's predicted recovery, with the PRD §13 "early estimate" label before 60 training days. Pure `build_evening_payload` is unit-tested; the I/O shell prunes 404/410 dead subscriptions and no-ops if `VAPID_PRIVATE_KEY` / `VAPID_SUBJECT` are unset. `_load_vapid_private_key()` accepts either an inline PEM (with literal `\n` escapes for prod env vars) or a filesystem path (handy in local dev — point at `backend/vapid_private.pem`).
- `backend/scripts/generate_vapid.py` — emits a P-256 ECDSA keypair using the `cryptography` lib (already a dep, no `py-vapid` needed). Writes `vapid_private.pem` + `vapid_public.txt`; both are gitignored.
- `backend/api/data.py` — `/api/dashboard`, `/api/receipt`, `/api/whatif`, `/api/plan`, `/api/profile`, `/api/wallet`. Each endpoint resolves the active user via `db.client.resolve_active_user_id(DEMO_EMAIL)` — prefers the most-recently-connected real WHOOP user, falls back to the demo user when nobody's connected yet. Swap this single helper for a session lookup when multi-user auth lands.
- `backend/api/checkin.py` — `GET/POST /api/checkin`.
- `backend/api/push.py` — `POST /api/push/subscribe` and `/unsubscribe`. Endpoint is the natural unique key on `push_subscriptions`; re-subscribes update in place.
- `backend/api/whoop.py` — `GET /api/whoop/connect`, `GET /api/whoop/callback` (HMAC-verified state cookie, marked `secure=True` in prod), `GET /api/whoop/status` (count of connected users), `POST /api/whoop/backfill` (manual trigger — schedules backfill in a `BackgroundTask`), `POST /api/whoop/backfill-sync` (synchronous diagnostic that returns the actual exception traceback in the JSON body — slow, debug-only). The OAuth callback schedules `_backfill_after_connect` so a 180-day pull starts the moment a user authorizes; the task `print()`s START / OK / FAILED with traceback so failures are visible in Railway logs even when uvicorn's log config silences our logger.
- `backend/db/client.py` — `resolve_active_user_id()` is the single seam between "demo data" and "real-user data". `open_pool()` passes `statement_cache_size=0` so the same DSN works against direct Postgres (local dev) and Supabase's transaction-mode pgbouncer pooler (prod, IPv4-only, port 6543).
- `frontend/components/CheckinCTA.tsx` — dashboard card that fetches `/api/checkin` on mount and shows either "Log today's check-in" (button → `/checkin`) or "Logged ✓" (with edit link). Solves the "where's the check-in button?" UX problem (the nav tab was easy to miss).
- `frontend/components/ConnectWhoopCTA.tsx` — dashboard card that polls `/api/whoop/status` and renders either a **Connect WHOOP** button (when `connected_users === 0`) or a "✓ connected" badge. The button links straight to `${API_URL}/api/whoop/connect`; clicking starts the OAuth dance, the callback fires `_backfill_after_connect`, and the user bounces back to the live frontend at `/?connected=1`.
- `frontend/components/EnableNotificationsButton.tsx` — opt-in push subscribe flow. Uses `useSyncExternalStore` with **module-level cached snapshot objects** so React 19's `react-hooks/set-state-in-effect` rule is satisfied without disabling lints. Hides itself when `NEXT_PUBLIC_VAPID_PUBLIC_KEY` is unset.
- `frontend/components/ErrorState.tsx` — used everywhere. Detects `→ 503` in the hint and renders a **"Your model isn't ready yet"** empty state instead of raw error text. New WHOOP users hitting `/plan`, `/profile`, `/wallet`, `/whatif` before the first nightly retrain see a friendly explanation.
- `frontend/lib/api.ts` — `resolveApiUrl()` validates `NEXT_PUBLIC_API_URL` actually starts with `http://` or `https://`; if not (e.g. an env-var swap on Vercel pasted a VAPID key here by mistake), falls back to a hardcoded prod Railway URL. Localhost dev still hits `:8000`. The frontend self-heals against env-var misconfiguration.
- `frontend/lib/push.ts` — `detectSupport()` + `enablePush()` helpers. `urlBase64ToUint8Array` returns `Uint8Array<ArrayBuffer>` (not the default `ArrayBufferLike`) to satisfy TS strict mode against `pushManager.subscribe`.
- `backend/api/webhooks.py` — `POST /api/whoop/webhook` (HMAC-verified). Re-pull is scheduled via FastAPI `BackgroundTasks` (not `asyncio.create_task`, which would orphan the coroutine and let GC collect it mid-run).
- `backend/db/migrations/` — apply ordered SQL files to existing databases when `schema.sql` gains a table after the project has been deployed (e.g. `001_push_subscriptions.sql`).
- `backend/CRONS.md` — Railway dashboard schedules (Railway crons aren't configured in `railway.json`; they're per-service in the UI).

## Commands

### Frontend (`cd frontend`)

```bash
npm run dev      # next dev — http://localhost:3000
npm run build    # next build — run before claiming a frontend change works
npm run lint     # eslint
```

### Backend (`cd backend`, with `.venv` activated)

```bash
uvicorn api.main:app --reload --port 8000   # dev server
pytest -x                                    # all tests, stop on first failure
pytest tests/test_features.py::test_pure -x  # single test
ruff check .                                 # lint (configured in pyproject.toml: E,F,I,UP,B; line-length 100)
ruff format .                                # format
```

`pyproject.toml` sets `pythonpath = ["."]` and `testpaths = ["tests"]`, so run `pytest` from `backend/`.

### Pre-commit gate

```bash
cd backend  && pytest -x
cd frontend && npm run lint && npm run build
```

## Frontend: Next.js 16 caveat

`frontend/CLAUDE.md` re-exports `frontend/AGENTS.md`, which warns:

> This version of Next.js has breaking changes — APIs, conventions, and file structure may differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` before writing any code. Heed deprecation notices.

Treat any Next.js API you "remember" as suspect; verify against the in-repo docs before using it.

## Architecture: the load-bearing invariants

These come from the PRD and are non-negotiable. Violating them silently breaks the product.

1. **`build_feature_matrix` must be a pure function** (`backend/ml/features.py`). No hidden state, no DB reads inside the inner transform. Counterfactual replay (Tier-2 feature D) and the inverse planner both depend on being able to re-run the same input through the same transform deterministically. There is a `tests/test_features.py::test_pure` test guarding this.

2. **Never use random `train_test_split` / `KFold` on this data.** Always `TimeSeriesSplit` + `RidgeCV`. Random splits leak the future and make the model look great in validation and useless in production. There is a `test_no_future_leakage` test asserting `val_idx > train_idx.max()`.

3. **SHAP integrity:** `base_value + Σ contributions ≈ prediction` within 0.01 must always hold. `shap.LinearExplainer` is exact for Ridge — if this test fails, the explainer was fit on the wrong reference data (use `pipeline[:-1].transform(X_train)`, not raw `X_train`). Test: `tests/test_shap_integrity.py`.

4. **Inverse planner uses `scipy.optimize.minimize` with SLSQP** on the trained Ridge coefficients, with hard physiological bounds (sleep ∈ 5–10h, strain ∈ 0–21, alcohol ≥ 0). When infeasible, return the closest reachable recovery and which constraint hit its bound — do not silently return a degenerate plan.

5. **Honesty rules (PRD §13) — enforced in UI copy:**
   - ❌ "Alcohol costs you 11 points." → ✅ "On days you logged alcohol, your model predicted 11 points lower."
   - ❌ "You should sleep more." → ✅ "Days with longer sleep had higher predicted recovery."
   - ❌ Any medical claim. Ever.
   - Before day 60 of data, every insight is labeled "early estimate" with a confidence interval (`ConfidenceLabel` component).

## Data flow (one request lifecycle)

User clicks **Connect WHOOP** on the live frontend → browser navigates to `<railway>/api/whoop/connect` → OAuth dance → `<railway>/api/whoop/callback?code&state` → backend exchanges code for tokens, upserts `users` + `whoop_tokens`, schedules `_backfill_after_connect` as a FastAPI `BackgroundTask`, and `RedirectResponse`s to `${FRONTEND_URL}/?connected=1`. Backfill runs server-side: 180 days of paged WHOOP data into `recoveries` / `cycles` / `sleeps` / `workouts`. The 4 AM `workers/safety_net.py` cron + webhook re-pulls keep that data fresh.

User submits daily check-in (`checkins` table) via `api/checkin.py`. The 4:30 AM `workers/train_now.py` cron calls `build_feature_matrix`, retrains the Ridge pipeline, pickles it to `backend/ml/artifacts/` (gitignored, ephemeral on Railway), runs `LinearExplainer`, and writes per-feature contributions to `shap_values`. Frontend reads predictions + receipts via FastAPI; the inverse planner (`POST /api/plan` → `ml/solve.py`) is called on demand.

`api/data.py` uses `db.client.resolve_active_user_id()` to pick *who* the dashboard belongs to — the most recently-connected real WHOOP user, or the demo user when nobody's connected. The synth generator (`backend/synth/generator.py`) is what seeds the demo user; once a real user clicks Connect, the dashboard switches to their data automatically.

Independent secondary loop (Web Push): the browser registers a `PushSubscription` via `frontend/lib/push.ts` (triggered by `<EnableNotificationsButton>` on the dashboard) and POSTs it to `api/push.py`. The 9 PM `workers/notify_evening.py` cron joins `push_subscriptions` against the most recent `predictions` row per user and sends the forecast via `pywebpush`. The service worker (`frontend/public/sw.js`) handles `push` and `notificationclick` events.

## Environment

`backend/.env.example` lists the required vars: `DATABASE_URL`, `SUPABASE_JWT_SECRET`, `WHOOP_CLIENT_ID/SECRET/REDIRECT_URI/WEBHOOK_SECRET`, `FRONTEND_URL`, `ANTHROPIC_API_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_SUBJECT`, `USER_TIMEZONE`. Never commit a populated `.env`. Frontend uses `NEXT_PUBLIC_API_URL` to point at the backend, and `NEXT_PUBLIC_VAPID_PUBLIC_KEY` to enable the push-subscription UI. Generate the VAPID keypair once with `cd backend && .venv/bin/python -m scripts.generate_vapid` (uses the `cryptography` lib already in requirements; no `py-vapid` install needed).

CORS in `api/main.py` allows `http://localhost:3000` and `https://*.vercel.app` — extend the regex if deploying to a custom domain.

### Production deployment gotchas (we hit every one of these)

These are the load-bearing operational details. Don't skip.

1. **`DATABASE_URL` must use Supabase's IPv4 pooler URL, not the direct host.** Direct host `db.<ref>.supabase.co:5432` resolves to AAAA records only. Railway containers have flaky IPv6 egress, so `asyncpg.create_pool` times out at startup, the lifespan in `api/main.py` catches the exception, the app boots `/health` cleanly, and every DB endpoint then 500s with "DB pool not initialized." Use the **Transaction Pooler** URL from Supabase → Connect: `postgresql://postgres.<ref>:<password>@aws-<region>.pooler.supabase.com:6543/postgres`. Port **6543**, host `*.pooler.supabase.com`. URL-encode special chars in the password (`@`→`%40`, `$`→`%24`).

2. **`statement_cache_size=0` on the asyncpg pool** is required for the pooler URL above. The pooler runs pgbouncer in transaction mode; asyncpg's prepared-statement cache breaks because each query may land on a different backend connection. We pass it unconditionally so the same DSN shape works in local dev (direct connection, harmless override) and prod (pooler, mandatory).

3. **`backfill_user` must take a `Pool`, not a single `Connection`.** A 6-month paged WHOOP pull holds a connection across many HTTP calls; pgbouncer's idle-timeout will kill it mid-run and the bare `except Exception` in `_backfill_after_connect` will swallow the error. Code now uses `Pool.acquire()` per endpoint; `BackgroundTask` start/end is `print()`ed so Railway logs surface it.

4. **`backend/requirements.txt` must include the full ML stack.** A Day-2 slim version (OAuth-only) was tempting but leads to import-time failures on Railway after the data routes land, which Railway papers over by serving the previous build. Keep `requirements.txt` ≈ `requirements-full.txt` minus pure-dev tooling.

5. **`NEXT_PUBLIC_*` env vars are baked into the bundle at `next build` time.** Editing them on Vercel does NOT take effect on already-deployed builds. After changing them, **redeploy WITHOUT build cache** (Deployments → ⋯ → Redeploy → uncheck "Use existing Build Cache"). `frontend/lib/api.ts` defensively falls back to a hardcoded prod URL when the env var doesn't look like a valid URL — protects against env-var swap mistakes (e.g. pasting a VAPID key into the API URL slot).

6. **Railway crons are separate services per cron, sharing variables via `${{Recovery-Debt.NAME}}` references.** Putting a cron schedule on the web service converts it into a one-shot job and the API goes offline. Create one service per cron entry in `backend/CRONS.md`, set `Custom Start Command` and `Cron Schedule` on each, and reference env vars from the main `Recovery-Debt` service.

7. **WHOOP redirect URI is the backend callback, not the frontend URL.** Register `https://<railway>/api/whoop/callback` on developer.whoop.com and set the Railway env var `WHOOP_REDIRECT_URI` to match exactly. The user bounces back to `FRONTEND_URL` (the Vercel host) AFTER the callback runs.

8. **WHOOP OAuth state cookie needs `secure=True` in prod.** The connect handler sets `secure=is_https` based on whether `WHOOP_REDIRECT_URI` starts with `https://` — browsers will silently drop a `Secure=False` cookie set on an HTTPS origin, which surfaces as "Invalid OAuth state" 400s in `/callback`.

## Tier-1 differentiation features (the things WHOOP Coach can't do)

The project's recruiter signal is concentrated in three pages — when scoping changes, prefer protecting these over polishing elsewhere:

- **Inverse Planner** (`/plan`, `POST /api/plan` in `api/data.py`, `ml/solve.py`)
- **Sensitivity Profile** (`/profile`, `GET /api/profile`) — bar chart of Ridge coefficients with median + IQR across the last ~30 model versions
- **Cumulative SHAP Wallet** (`/wallet`, `GET /api/wallet`) — area chart of cumulative SHAP per feature category; re-explain historical days through the *current* model nightly so values stay comparable

## End-to-end smoke from a clean checkout

```bash
cd backend
.venv/bin/python -m synth.generator        # seed 180 days for demo user
.venv/bin/python -m workers.train_now      # train + write artifact + write tomorrow's prediction
.venv/bin/uvicorn api.main:app --reload    # backend on :8000
# in frontend/: npm run dev → :3000 lights up with real numbers
```

If `train_now` reports an integrity residual > 0.01, the SHAP explainer is fit on the wrong reference data — see invariant #3 above.

## Live diagnostics

When prod misbehaves, hit these endpoints in order:

```bash
curl https://<railway>/health           # → {"ok": true}  ← the app booted
curl https://<railway>/health/db        # → {"ok": true, "stage": "query"}  ← pool opened, SELECT 1 works
curl https://<railway>/api/whoop/status # → {"connected_users": N}
curl -X POST https://<railway>/api/whoop/backfill-sync  # → {"ok": true|false, "counts"|"traceback": ...}
```

`/health/db` returning `{"ok": false, "stage": "pool"}` means the pool failed to open at startup — almost always the IPv4-pooler issue (gotcha #1). `/api/whoop/backfill-sync` is a synchronous version of `/backfill` that returns the actual exception traceback in the JSON body — invaluable when Railway logs aren't easily accessible.
