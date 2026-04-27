# Recovery Debt — Final PRD

*Date: 2026-04-27*
*Sources merged: Recovery_Debt_Project_Plan.pdf + Recovery_Debt_Data_Model_and_ML.pdf + 2 audio walkthroughs*

---

## TL;DR

A personal **web app (PWA)** that connects to your WHOOP, learns *your* body's patterns from the last 6 months of data plus a 15-second daily check-in, and turns your recovery score into a **bank-account ledger**. Each day shows up as a deposit or withdrawal with an **itemized receipt** ("−10 sleep, −6 alcohol, −2 late meeting"), a running balance, and a 3-day forecast. Built in 3 weeks as a portfolio project and a real personal tool.

---

## 1. The Goal (one sentence)

> Build a web app that explains *why* your WHOOP recovery score is what it is — in numbers, in plain English, every single day.

---

## 2. The Problem (in very easy words)

WHOOP gives you a number every morning (0–100). It does **not** tell you why. You don't know if it's the wine, the late dinner, the stressful meeting day, or the leg workout from two days ago.

It's like checking your credit score, seeing it dropped 50 points, and the bank refusing to show you the credit card statement. You know something is wrong. You have no idea which purchase did it.

**We're fixing that.** The app is the credit card statement for your body.

---

## 3. Who It's For

- **You first** — single user, your own body, your own WHOOP. Most-used user is yourself.
- Later: anyone who wears a WHOOP and wants explanations, not just scores.
- Also a **portfolio piece** for AI-engineer hiring managers.

---

## 4. Web App vs Native App — Decision

**Decision: Web app, built as a PWA (Progressive Web App).**

| Option | What it means | Pick? |
|---|---|---|
| Website only | Open in Chrome/Safari, no install | OK |
| Native iOS/Android | Install from App Store | No |
| **PWA (web that installs like an app)** | Website + "Add to Home Screen" makes it act like an app | **Yes** |

**Why PWA wins:**
1. **Recruiters click a link.** They will not install an iOS app. A live URL = they open it.
2. **One codebase, three weeks.** Native = iOS + Android + a web demo. Web = build once.
3. **WHOOP is API-based.** No GPS, camera, or HealthKit needed, so native gives no extra power.
4. **Cheaper.** Vercel + Railway = a few dollars/month. App Store = $99/year + approval friction.
5. **Best of both worlds.** PWA gives home-screen install, push notifications, offline check-in — all from a normal website.

The Next.js stack already supports PWA out of the box. ~1 hour of extra work in Week 3.

---

## 5. Success Criteria

| Goal | How we measure it |
|---|---|
| Connects to WHOOP, pulls 6 months of data | OAuth flow works end-to-end, data lands in DB |
| Predicts tomorrow's recovery | Model RMSE < 10 points on held-out days |
| Explains today's score in plain English with numbers | Card shows top 5 SHAP contributors |
| Ledger feels like a banking app | Running 7-day balance + 3-day forecast on screen |
| Recruiter can demo without a WHOOP | Demo mode with synthetic data works |
| Deployed publicly | Live link on Vercel + Railway |
| Installable on phone | "Add to Home Screen" works on iOS + Android |
| Honest about uncertainty | First 60 days show "early estimate" labels + 80% prediction intervals |

---

## 6. Features

### Core (must-ship, weeks 1–3)
1. **WHOOP login + auto-sync** — OAuth 2.0 + webhooks; backfill 6 months on first connect; daily safety-net cron re-fetches last 3 days in case a webhook was dropped.
2. **15-second daily check-in** — sliders + yes/no toggles for: alcohol, caffeine, stress (1–10), late meal, illness, travel, menstrual day (optional).
3. **Personal ML model** — retrained nightly at 4 AM local time, trained only on *your* data.
4. **Recovery Debt ledger** — banking-style transaction list, running 7-day balance, 3-day forecast.
5. **SHAP itemized receipt** — top 5 contributors per day in plain English ("sleep −10, alcohol −6, late meeting −2").
6. **"What if I…" simulator** — sliders for tomorrow's strain and sleep; predicted recovery and forecast balance update live.
7. **PWA support** — manifest + service worker; "Add to Home Screen"; push notifications when morning score arrives; offline check-in.
8. **Demo mode** — synthetic user with realistic data so anyone can click through without owning a WHOOP.

### Stretch (week 3 if time)
9. **LLM journal parser** — instead of clicking sliders, type "two beers, late dinner, boss yelled at me" and Claude turns it into structured fields. Use **strict JSON schema** output (deterministic parser, NOT a chatbot).
10. **Google Calendar integration** — auto-fill meeting density.
11. **Weather API** — temperature and barometric pressure as features.

---

## 7. The Tech Stack — Four Rooms in a House

Each "room" has one job and one main tool.

### Room 1 — The Front Door (what the user sees)
| Piece | Tool | Why |
|---|---|---|
| Framework | **Next.js 14 + TypeScript** | Modern React; recruiters expect it; TypeScript catches bugs early |
| Styling | **Tailwind CSS** | Utility classes, no custom CSS |
| UI components | **shadcn/ui** | Drop-in buttons, dialogs, forms; professional out of the box |
| Charts | **Recharts** | Easy line + bar charts for the dashboard |
| PWA | **next-pwa** (manifest + service worker) | Installable on phone home screen |
| Hosting | **Vercel** | Free, one command to deploy |

### Room 2 — The Kitchen (where the work happens)
| Piece | Tool | Why |
|---|---|---|
| Backend | **FastAPI (Python)** | Plays nicely with scikit-learn and pandas |
| Hosting | **Railway** (or Fly.io) | Cheap; supports the nightly retraining cron |

### Room 3 — The Pantry (where data lives)
| Piece | Tool | Why |
|---|---|---|
| Database + auth + storage | **Supabase (Postgres)** | Three services in one |

### Room 4 — The Brain (the ML)
| Piece | Tool | Why |
|---|---|---|
| Model | **Ridge Regression** (scikit-learn) | Linear, fast, hard to overfit; SHAP is *exact* on linear models |
| Validation | **TimeSeriesSplit + RidgeCV** | Time-series split is mandatory — random KFold leaks future data |
| Explanations | **shap.LinearExplainer** | Computationally cheap; exact for Ridge |
| LLM (stretch) | **Anthropic Claude API** | Strict JSON schema parser, not a chatbot |

### Outside the House
| Piece | Tool | Why |
|---|---|---|
| Data source | **WHOOP OAuth 2.0 + webhooks** | Official API for reading data + real-time updates |

---

## 8. Database Schema (Postgres / Supabase)

8 tables. UUID primary keys. Every per-day table has `UNIQUE (user_id, day)` so re-pulls are idempotent.

| Table | Holds |
|---|---|
| `users` | account row + linked WHOOP user id |
| `whoop_tokens` | access + refresh tokens (refresh on the fly; access expires in 1h) |
| `recoveries` | per-day: recovery_score, hrv_rmssd_ms, rhr_bpm, spo2_pct, skin_temp_c |
| `cycles` | per-day: strain, kilojoule, avg_hr, max_hr, start/end timestamps |
| `sleeps` | per-day: in_bed_ms, awake_ms, light/deep/rem_ms, efficiency, consistency, respiratory rate, sleep_need_ms, disturbances |
| `workouts` | per-workout: start/end, strain, sport_id, hr stats, kilojoule, distance_m, zone_durations (JSONB) |
| `checkins` | per-day user log: alcohol_drinks, caffeine_mg, stress_1to10, late_meal, ill, traveling, menstrual_day, raw_text |
| `predictions` | per-target-day: predicted_recovery, 80% lower/upper bound, model_version |
| `shap_values` | per-prediction: feature_name → contribution (in recovery points) |
| `models` | per-version: trained_at, n_training_days, metrics (r2/rmse/mae), artifact_path |

---

## 9. The ML, in Plain English

### What we're predicting
A number from 0 to 100 (tomorrow's recovery). That makes this a **regression** problem.

### What we feed the model (~30 features in 5 buckets)

**Bucket A — last night's sleep** (strongest signal): duration, efficiency, consistency, REM minutes, deep minutes, disturbance count, respiratory rate, 3-day sleep debt.

**Bucket B — yesterday's behavior** (from check-in for D-1): alcohol drinks, caffeine, stress, late meal, meeting minutes, meetings after 8pm, travel, illness.

**Bucket C — yesterday's physiology** (from WHOOP for D-1): strain, avg HR, recovery, HRV, RHR.

**Bucket D — recent trends** (rolling windows): 3- and 7-day averages of strain, HRV, RHR, recovery; 28-day z-scores for HRV and RHR.

**Bucket E — external context**: weather max temp, barometric pressure, menstrual phase one-hot.

### The training rule
> More features than data points = the cardinal sin of personal modeling.

Start with these ~30. Prune via L1 or by watching SHAP importance after a few weeks.

### Missing data
- Median imputation **on the user's own data** (not a global default).
- Add a binary `was_missing_X` column for any feature missing >10% of the time — "missing" itself can carry signal.

### Training loop (runs nightly at 4 AM local)

```python
def nightly_train(user_id):
    df = build_feature_matrix(user_id)   # one row per day, last ~180 days

    if len(df) < 21:
        # cold start: skip training; UI shows "early estimate"
        return

    # Time-series split — NEVER random KFold on time-series
    val_size = max(7, int(0.2 * len(df)))
    train, val = df.iloc[:-val_size], df.iloc[-val_size:]

    pipeline = Pipeline([
        ("impute", SimpleImputer(strategy="median")),
        ("scale",  StandardScaler()),                 # Ridge needs scaled features
        ("ridge",  RidgeCV(alphas=[0.1, 1, 10, 100],
                           cv=TimeSeriesSplit(n_splits=5))),
    ])
    pipeline.fit(train.X, train.y)

    metrics = {"r2": ..., "rmse": ..., "mae": ..., "n_train": ..., "n_val": ...}

    # Refit on full window for production
    pipeline.fit(df.X, df.y)

    # SHAP — LinearExplainer is exact and fast on Ridge
    explainer = shap.LinearExplainer(pipeline.named_steps["ridge"],
                                     pipeline[:-1].transform(df.X))

    save_model(user_id, pipeline, explainer, metrics, version=date.today())
    predict_and_store(user_id, target=date.today() + timedelta(days=1))
```

### Why Ridge first
- **Linear → SHAP is exact**, not approximate.
- **Coefficients are themselves interpretable.**
- **Cheap.** Trains in milliseconds, even on years of data.
- After 90+ days of data, A/B against a Gradient Boosting model (LightGBM + TreeExplainer) and keep whichever has lower validation MAE.

---

## 10. The Recovery Debt Math

```
baseline           = median(recovery_score over last 28 days)
delta(d)           = recovery_score(d) - baseline
debt_balance(today) = -sum(delta over last 7 days)        # positive = in debt
forecast(today+3)   = debt_balance(today)
                      - sum(predicted_recovery(d) - baseline
                            for d in [today+1, today+2, today+3])
```

**UI implication:** every row in the ledger shows the recovery score, the delta from baseline (e.g. "−9 pts"), and SHAP's top contributors. The headline number at the top is `debt_balance(today)`.

---

## 11. The 3-Week Plan

Assumes ~25–30 hours/week. Add a buffer to Week 1 if learning the stack.

### Week 1 — Plumbing (the data pipeline)
**Goal:** your own WHOOP data flowing into the DB and rendering on a basic page.
- Set up Next.js, FastAPI, Supabase project.
- Register WHOOP developer app; implement OAuth.
- Backfill last 6 months (paginate via `next_token`).
- Subscribe to `recovery.updated`, `sleep.updated`, `workout.updated` webhooks.
- Add a daily safety-net cron that re-fetches the last 3 days.
- Basic dashboard: recovery score line chart over time.

**End-of-week test:** open the app, log in, see 6 months of recovery as a line chart.

### Week 2 — Brain (model + explanations)
**Goal:** predicts tomorrow's recovery and explains today in plain English with numbers.
- Build daily check-in form (alcohol, stress, meals, sick, travel).
- Engineer features (Buckets A–E, ~30 columns) plus `was_missing_X` flags.
- Train Ridge Regression with TimeSeriesSplit + RidgeCV.
- Set up nightly cron on Railway.
- Add `shap.LinearExplainer`; persist contributions in `shap_values`.
- Display per-day "itemized receipt" card on the dashboard (top 5 contributors only).
- Unit test: SHAP base value + sum of contributions = prediction (within 0.01).

**End-of-week test:** open the app and see a card: *"Your recovery dropped 18 points today because: sleep −10, alcohol −6, late meeting −2."*

### Week 3 — Polish (ledger, simulator, PWA, deploy)
**Goal:** ship the standout features and a clean public demo.
- Banking-style ledger UI: transaction list + running balance + 3-day forecast.
- "What if I…" simulator: sliders for tomorrow's strain/sleep, predicted recovery updates live.
- *(Stretch)* LLM journal parser via Claude API with strict JSON schema.
- PWA manifest + service worker → installable on phone, push notifications.
- Demo mode with synthetic data (realistic covariance — see "Verification" below).
- Deploy frontend (Vercel) + backend (Railway). Clean README. Record a 60–90 second Loom showing one real, surprising insight from your own data.

**End-of-week test:** send the live link to a friend; they understand the app in under a minute and can install it on their phone.

---

## 12. Pre-Ship Verification Checklist

Things that will silently break the project if missed:

- [ ] **Time-series split, never random.** Random splits leak future data and make models look great in validation, useless in production.
- [ ] **Webhooks confirmed working** with a manual sample. WHOOP webhook setup is fiddly — silent failures cost a day of data.
- [ ] **Ridge needs scaled features.** `StandardScaler` is not optional.
- [ ] **SHAP integrity test:** `base_value + sum(contributions) == prediction` within 0.01. If not, the explainer was built on the wrong reference data.
- [ ] **Cap displayed SHAP contributions at the top 5 per day.** More than that is noise.
- [ ] **First 60 days:** every insight labeled "early estimate" + 80% prediction interval shown.
- [ ] **No causal claims, ever.** *"On days you logged alcohol, your model predicted 11 points lower"* — never *"alcohol costs you 11 points."*
- [ ] **Demo mode synthetic data preserves realistic covariance** (sleep ↓ → RHR ↑, HRV ↓), or the model output looks insane.
- [ ] **Token refresh** runs on the fly. WHOOP access tokens expire after 1 hour.

---

## 13. Risks & Honest Caveats

| Risk | Mitigation |
|---|---|
| **Cold start.** Models need data. <60 days of logs = unstable explanations. | Skip training when n < 21 days. Show "early estimate" labels and 80% prediction intervals through day 60. |
| **Correlation, not causation.** SHAP explains the *model*, not your biology. Alcohol may be a passenger on the same sinking ship as stress + late dinners. | Frame insights as *"on days you logged X, your model predicted Y points lower."* Never *"X costs you Y points."* |
| **No medical claims.** Ever. The app finds patterns; it is not a doctor. | UI never says "alcohol is bad for you" or "you should sleep more." |
| **Demo problem.** Recruiters don't have a WHOOP. | Demo mode with synthetic data from day one. (Bonus: it's good engineering practice — separates data sources from UI logic.) |
| **User fatigue.** Daily logging breaks within a week if there's friction. | 15-second cap on the daily form. Sliders + toggles only. LLM journal parser as escape hatch in week 3. |
| **Algorithm dependence.** Risk that the ledger starts dictating life choices (skip dinner with friends because the forecast says so). | App **suggests, never commands.** Frame insights as observations, not orders. |

---

## 14. Design Principles (the brand voice)

These come from the audio walkthroughs and matter for UI copy:

- **The itemized receipt.** Every score gets broken down. No black boxes.
- **The bank account metaphor.** Deposits, withdrawals, balance, overdraft. Humans understand money; they don't intuitively understand a "0–100 recovery score."
- **Honesty is a feature, not a flaw.** Confidence intervals and "early estimate" labels build trust. A junior dev hides model flaws; a senior dev surfaces them.
- **Suggest, never command.** The app gives you the receipt — *you* decide what to do with it.
- **Death of the dropdown.** Forms kill habit-tracking. Sliders, toggles, and (stretch) free-text journals.
- **AI as a tool, not a personality.** The LLM is a deterministic JSON parser, not a chatbot.

---

## 15. Why This Is a Strong Portfolio Project

Hits every box an AI-engineering hiring manager looks for, in one focused project:

- **Real ML** — regression, feature engineering with lagged + rolling features, time-series validation, nightly retraining loop.
- **Model explainability** — SHAP (Linear variant for cost), with an integrity unit test.
- **LLM integration** — strict-JSON parser; AI used as a tool, not the whole product.
- **Full-stack delivery** — OAuth 2.0, webhooks, Postgres schema, scheduled jobs, frontend, PWA, public deploy.
- **Memorable hook** — "Recovery Debt" pitches in one sentence.
- **Honest framing of model limits** — the judgment that separates an engineer from a tutorial-follower.

---

## 16. Differentiation Roadmap (vs. WHOOP Coach)

WHOOP Coach (the GPT-based in-app chatbot) already answers *"why is my recovery low today?"* — so the basic explanation use case is no longer unique. Recovery Debt's edge has to be **structural**: things Coach architecturally cannot do. Coach is a generic LLM, locked to WHOOP's data silo, prose-only, reactive Q&A, with no per-user model. That architecture has fixed blind spots. The features below are picked to exploit them.

**The "Win" Thesis.** Recovery Debt builds **three capability classes** on the same personal Ridge backbone — Coach has zero of them:
1. **Forward prediction with numeric attribution** (already in the PRD — SHAP receipt + 3-day forecast).
2. **Backward attribution and counterfactual replay** — model-based "what if last Tuesday had been different?"
3. **Inverse planning** — given a target, solve for the required behaviors.

### Tier 1 — Ship in the 3-week build

**A. Inverse Recovery Planner** *("Solve for Saturday")*
Type a recovery target for race day; the app solves a small QP on the Ridge model — minimize deviation from your typical day subject to physiological bounds — and returns the required sleep / strain / behavior plan. Coach is forward-only and cannot do constrained optimization. New table `goals`, new endpoint `POST /api/goals/solve`, new page `/plan`. Killer UX: when the target is infeasible, return the closest achievable recovery and which constraint hit its bound.
**Effort:** Medium (3–4 days). **Recruiter signal:** High.

**B. Personal Sensitivity Profile** *("Body Personality" page)*
Aggregate the Ridge coefficients across the last 30 nightly retraining versions and surface their median + IQR per feature. Reads like *"your sleep-duration sensitivity: 4.2 pts/hour (stable)"* vs. *"your stress sensitivity: 1.1 pts/level (still learning)."* This phrase is **only** expressible if a per-user model exists — Coach gives the same advice to everyone. New page `/profile`.
**Effort:** Low (1 day). **Recruiter signal:** High.

**C. Cumulative SHAP Wallet** *("Year-in-Review for Your Body")*
SQL aggregation over `shap_values` grouped by feature category (sleep / behavior / strain / external / trend) → running cumulative attribution per category over months. *"Days you logged alcohol: −412 pts across the year. Sleep consistency: +680."* Coach has no longitudinal attribution. **Important:** to compare across model versions, re-explain all historical days through the *current* model nightly. New page `/wallet`.
**Effort:** Low (1.5 days). **Recruiter signal:** Medium-High.

### Tier 2 — Stretch (post-launch / v2; signal direction in README)

- **D. Counterfactual Replay** — mutate one feature on a past day, re-run the feature pipeline forward through the rolling-window cascade, predict with each day's contemporaneous `model_version`. *Design note for v1:* build `build_feature_matrix` as a **pure function** so this is trivial later.
- **E. Calendar-Aware Proactive Forecasting** — upgrade the optional Calendar integration from retrospective to prospective; pair with the Inverse Planner restricted to controllable features; push notif at 9 PM with the smallest behavioral lever.
- **F. Multi-Source Fusion with Provenance** — tag every feature with `source ∈ {whoop, strava, calendar, weather, checkin}`; group SHAP contributions by source so each receipt shows *"73% of today's explanation came from WHOOP, 18% from your check-in, 9% from weather."*

### What I deliberately did NOT add

- Voice journaling (UX add, not structural moat — the existing LLM JSON parser is the structurally interesting part)
- Friend / social accountability (orthogonal to AI-engineering recruiter signal)
- Privacy-preserving local inference via ONNX.js (no real privacy story when the data already lives on your server)
- Symptom correlations / medical journaling (medical-claim risk for a 3-week portfolio)
- Athletic periodization (drifts from the explainability core)
- **Beating Coach at being Coach** — Coach has the in-app distribution, the head start, and WHOOP's data team. Compete on capabilities Coach lacks, not capabilities Coach already has.

### Elevator pitch (interview / portfolio)

> *"WHOOP Coach is a generic LLM with the user's data piped into the prompt — it's reactive Q&A and gives prose, not numbers. Recovery Debt is a different paradigm: a per-user Ridge model with SHAP attribution that does three things Coach architecturally can't — forward prediction with exact numeric receipts, backward attribution aggregated into a year-in-review, and inverse planning where you give the app a recovery target and it solves for the behaviors required to hit it. The interesting engineering wasn't beating Coach; it was building the personal-model + explainability + optimization stack honestly, including the cold-start problem and the correlation-vs-causation gap."*

### Verification — how to prove the differentiation actually works

Before claiming Recovery Debt "stands out", check these in the Loom / portfolio:

1. **Side-by-side screenshot.** Coach's prose answer next to Recovery Debt's SHAP receipt for the same day. *No code; just one frame.*
2. **Inverse Planner demo** — type a target, watch the plan appear. Coach has no equivalent screen.
3. **Sensitivity Profile demo** — show the per-feature coefficient bar chart with stability whiskers.
4. **Wallet demo** — area chart of cumulative SHAP by category over months.
5. **Honest framing audit** — grep the codebase for causal language (*"causes", "is bad for", "should"*). All such strings get rewritten per §14.
6. **Cold-start audit** — until 60 days of data, every Tier-1 feature shows an "early estimate" label and a confidence interval.
7. **Architecture diagram** — one Mermaid figure showing forward + backward + inverse all consuming the same `models` artifact: the "three capability classes on one backbone" story made visible.

If all seven hold, the differentiation is real and defensible — not because Recovery Debt beats Coach at being Coach, but because it does three things Coach is architecturally incapable of.

---

## 17. Open Questions

Things to decide before kicking off Week 1:

1. **Time zone handling.** Where do we get user local time for the 4 AM cron? (Browser → store on `users` row at signup.)
2. **WHOOP "day" boundary.** Cycles use a custom day boundary (afternoon-to-afternoon). Reconfirm before Week 2 feature engineering.
3. **Notification opt-in.** Default off, prompt after Day 7? Or off until user enables?
4. **Push notification provider.** Vercel/Web Push API directly, or a service like OneSignal?
5. **Synthetic-data generator** — write our own, or use a small library (e.g. SDV)?
6. **Inverse-planner solver** (new) — `scipy.optimize.minimize` with SLSQP, or `cvxpy`? *(Recommendation: scipy — fewer deps.)*

---

## 18. Next Steps

1. You review this PRD.
2. If approved → write detailed implementation plan (the writing-plans skill).
3. Then start Week 1.

*Source documents (saved to `docs/`):*
- `Recovery_Debt_Project_Plan.pdf`
- `Recovery_Debt_Data_Model_and_ML.pdf`
- `transcripts/itemized_receipt.txt`
- `transcripts/bank_account.txt`
