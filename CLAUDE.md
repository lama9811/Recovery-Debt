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
- `backend/workers/backfill.py` — real-WHOOP 6-month pull with refresh-token grant.
- `backend/workers/safety_net.py` — re-pull last 3 days for every user. 4 AM cron.
- `backend/workers/train_now.py` — end-to-end retrain CLI (Day 10 cron entry point).
- `backend/workers/notify_evening.py` — 9 PM Web Push: tomorrow's predicted recovery, with the PRD §13 "early estimate" label before 60 training days. Pure `build_evening_payload` is unit-tested; the I/O shell prunes 404/410 dead subscriptions and no-ops if `VAPID_PRIVATE_KEY` / `VAPID_SUBJECT` are unset.
- `backend/api/data.py` — `/api/dashboard`, `/api/receipt`, `/api/whatif`, `/api/plan`, `/api/profile`, `/api/wallet`. All scoped to the demo user via `_get_user_id()`; swap that for a session lookup when real-user auth lands.
- `backend/api/checkin.py` — `GET/POST /api/checkin`.
- `backend/api/push.py` — `POST /api/push/subscribe` and `/unsubscribe`. Endpoint is the natural unique key on `push_subscriptions`; re-subscribes update in place.
- `backend/api/webhooks.py` — `POST /api/whoop/webhook` (HMAC-verified).
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

WHOOP OAuth (`api/whoop.py`) → tokens stored in Supabase → `workers/backfill.py` + `api/webhooks.py` + 4 AM `workers/safety_net.py` cron populate `recoveries` / `cycles` / `sleeps` / `workouts`. User submits daily check-in (`checkins` table) via `api/checkin.py`. Nightly cron (`workers/train_now.py`, scheduled per `backend/CRONS.md`) calls `build_feature_matrix`, retrains the Ridge pipeline, pickles it to `backend/ml/artifacts/` (gitignored), runs `LinearExplainer`, and writes per-feature contributions to `shap_values`. Frontend reads predictions + receipts via FastAPI; the inverse planner (`POST /api/plan` → `ml/solve.py`) is called on demand.

For demo work without a real WHOOP, `backend/synth/generator.py` seeds the same tables for `demo@recoverydebt.local`. Every `api/data.py` endpoint resolves that email by default — when real-user auth lands, swap `_get_user_id()` for a session lookup.

Independent secondary loop: the browser registers a `PushSubscription` via `frontend/lib/push.ts` (triggered by `<EnableNotificationsButton>` on the dashboard) and POSTs it to `api/push.py`. The 9 PM `workers/notify_evening.py` cron joins `push_subscriptions` against the most recent `predictions` row per user and sends the forecast via `pywebpush`. The service worker (`frontend/public/sw.js`) handles `push` and `notificationclick` events.

## Environment

`backend/.env.example` lists the required vars: `DATABASE_URL`, `SUPABASE_JWT_SECRET`, `WHOOP_CLIENT_ID/SECRET/REDIRECT_URI/WEBHOOK_SECRET`, `ANTHROPIC_API_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_SUBJECT`, `USER_TIMEZONE`. Never commit a populated `.env`. Frontend uses `NEXT_PUBLIC_API_URL` to point at the backend, and `NEXT_PUBLIC_VAPID_PUBLIC_KEY` to enable the push-subscription UI (button hides itself when unset). Generate the VAPID keypair once with `pip install py-vapid && vapid --gen` — see `backend/CRONS.md` for the full flow.

CORS in `api/main.py` allows `http://localhost:3000` and `https://*.vercel.app` — extend the regex if deploying to a different host.

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
