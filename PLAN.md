# Recovery Debt — Build Plan (Simple Version)

3 weeks. ~25 hours per week. ~15 working days total. No jargon.

---

## What You're Building (1 sentence)

A web app that connects to your WHOOP, learns *your* body's patterns, and shows you *why* your recovery score is what it is — like a bank statement for your body.

---

## Before You Start (one-time setup, ~1 hour)

Get these accounts ready (all free):

- [ ] **GitHub** account (you already have it: `lama9811`)
- [ ] **WHOOP developer account** → https://developer.whoop.com/ (you'll register your app and get an API key)
- [ ] **Supabase** account → https://supabase.com (free tier — gives you a database + login system in one)
- [ ] **Vercel** account → https://vercel.com (free, for hosting the website)
- [ ] **Railway** account → https://railway.app ($5/mo, for hosting the Python backend)
- [ ] **Anthropic** API key → https://console.anthropic.com (only needed in Week 3 stretch)

Tools to install on your laptop:

- [ ] Node.js 20+ → https://nodejs.org
- [ ] Python 3.11+ (you already have it)
- [ ] VS Code or Cursor
- [ ] Git (already installed)

---

## Week 1 — The Plumbing 🔧

**Goal by Friday:** open your app, log in, see 6 months of your recovery scores as a line chart.

### Day 1 — Set up the empty house
- [ ] Create a new GitHub repo: `recovery-debt`
- [ ] Run `npx create-next-app@latest frontend` (Next.js + TypeScript + Tailwind)
- [ ] Make a `backend/` folder, set up FastAPI: `pip install fastapi uvicorn`
- [ ] Create a Supabase project, copy the connection string
- [ ] Push everything to GitHub

**End of day check:** `npm run dev` opens a blank Next.js page. `uvicorn main:app --reload` runs an empty FastAPI server.

### Day 2 — Connect to WHOOP
- [ ] Register your app on WHOOP developer portal — get `client_id` and `client_secret`
- [ ] Build the "Connect WHOOP" button on the frontend
- [ ] Build the OAuth flow: user clicks → redirects to WHOOP → comes back with an access token
- [ ] Save the token to your `whoop_tokens` table (refresh every hour)

**End of day check:** click "Connect WHOOP", approve, see "Connected!" on your screen.

### Day 3 — Pull 6 months of data
- [ ] Write a backfill script: page through `/v1/recovery`, `/v1/cycle`, `/v1/activity/sleep`, `/v1/activity/workout`
- [ ] Save into the 4 tables (`recoveries`, `cycles`, `sleeps`, `workouts`)
- [ ] Use `UNIQUE (user_id, day)` so re-pulls don't duplicate

**End of day check:** open Supabase, see ~180 rows in each table.

### Day 4 — Webhooks + safety net
- [ ] Set up webhooks: WHOOP pings your backend whenever new data is ready
- [ ] Add a daily cron (4 AM) on Railway that re-pulls the last 3 days as a safety net (in case a webhook was dropped)

**End of day check:** ask WHOOP support to fire a test webhook. See it land in your DB.

### Day 5 — First chart
- [ ] Build a basic dashboard page in Next.js
- [ ] Use Recharts to show a line chart of your recovery score over the last 180 days
- [ ] Deploy frontend to Vercel and backend to Railway (just to make sure deploys work early)

**Friday test:** open your live URL, log in, see your recovery chart. Take a screenshot. Celebrate. 🎉

---

## Week 2 — The Brain 🧠

**Goal by Friday:** open your app and see *"Your recovery dropped 18 points today because: sleep −10, alcohol −6, late meeting −2."*

### Day 6 — Daily check-in form
- [ ] Build a 15-second form: alcohol drinks (number), caffeine (mg), stress (1–10 slider), late meal (yes/no), sick (yes/no), traveling (yes/no)
- [ ] Save to a `checkins` table with `UNIQUE (user_id, day)`
- [ ] Make it mobile-friendly (you'll fill this out on your phone every morning)

**End of day check:** fill out today's check-in on your phone. See it in Supabase.

### Day 7 — Build the feature matrix
- [ ] Write a Python function: `build_feature_matrix(user_id)` that returns one row per day with ~30 columns
- [ ] Include lagged features: yesterday's strain, 2-day-ago sleep, 3-day average HRV, etc.
- [ ] Add `was_missing_X` flag for any feature that's null
- [ ] **IMPORTANT:** make this function pure — no hidden state. (Future you will thank you when you build counterfactual replay.)

**End of day check:** print the matrix shape: should be `(roughly 180, ~30)`.

### Day 8 — Train the model
- [ ] Use the pseudocode from PRD §9 — Ridge Regression with `TimeSeriesSplit` cross-validation
- [ ] **NEVER use random `train_test_split`** on time-series data — it leaks the future. The PRD is firm on this.
- [ ] Print R² and RMSE on the held-out tail of your data

**End of day check:** R² > 0.3 is fine for a personal model with limited data. RMSE under 12 is good.

### Day 9 — Add SHAP (the receipts)
- [ ] Use `shap.LinearExplainer` (it's exact for Ridge — no approximation)
- [ ] After every prediction, save the per-feature contributions to the `shap_values` table
- [ ] Write a unit test: `base_value + sum(contributions) == prediction` (within 0.01). If this fails, your explainer is broken.

**End of day check:** for one prediction, print: *"sleep −10, alcohol −6, strain +2, total prediction = 58."*

### Day 10 — Nightly cron + receipt UI
- [ ] On Railway, add a cron job that runs at 4 AM your local time:
  - Pull new WHOOP data
  - Retrain the model
  - Predict tomorrow's recovery
  - Save SHAP contributions
- [ ] On the frontend, add a "Today's Receipt" card that shows the **top 5** contributors (more is noise)

**Friday test:** open the app, see *"Your recovery dropped 18 points today because: …"* with real numbers from your real life. Screenshot. 🎉

---

## Week 3 — The Standout Features 🏆

**Goal by Friday:** ship the 3 things that beat WHOOP Coach. Then deploy publicly.

These are the **Tier 1 differentiation features** from PRD §16.

### Day 11 — The Ledger UI (banking style)
- [ ] Build the homepage: a list of "transactions" (each day = a row)
  - Each row: date, score, delta from baseline (e.g. "−9 pts"), top 3 SHAP contributors
- [ ] Add the running 7-day balance number at the top
- [ ] Add the 3-day forecast on the side

**End of day check:** the dashboard looks like your bank's transaction list, but for your body.

### Day 12 — The What-If Simulator
- [ ] Build a "What if I…" page with sliders: tomorrow's strain, tomorrow's sleep, planned alcohol
- [ ] As the user drags sliders, predicted recovery for tomorrow + the next 3 days updates live
- [ ] Show the cascade: dragging sleep down on Wednesday changes Thursday, Friday, and Saturday's forecast

**End of day check:** dragging sleep from 8h to 5h drops Friday's predicted recovery noticeably.

### Day 13 — The Inverse Planner (the killer feature)
This is the one Coach physically can't do. Take it slow.

- [ ] New page: `/plan`
- [ ] User input: "Target recovery: 75 by Saturday"
- [ ] Backend: solve a small optimization problem on the Ridge model — `scipy.optimize.minimize` with SLSQP
  - Find the (sleep, strain, alcohol) values that make the model predict ≥ 75
  - Stay within physiological bounds (sleep ∈ 5–10h, strain ∈ 0–21, alcohol ≥ 0)
- [ ] When infeasible: show *"Can't hit 75. Closest reachable: 71 if you sleep 9h Friday and skip the workout."*
- [ ] New table: `goals (id, user_id, target_day, target_recovery, solved_plan JSONB)`

**End of day check:** type a target → see a concrete plan appear. Coach has no equivalent screen.

### Day 14 — Sensitivity Profile + SHAP Wallet (the visual hits)
Two pages, both fast to build:

- [ ] `/profile` — bar chart of your Ridge coefficients per feature, with stability whiskers (median + IQR across the last ~30 model versions). Label each: "your sleep sensitivity: 4.2 pts/hour (stable)" or "your stress sensitivity: 1.1 pts/level (still learning)."
- [ ] `/wallet` — area chart of cumulative SHAP contribution per category over months. *"Days you logged alcohol cost you 412 pts this year. Sleep consistency: +680."*

**End of day check:** these two pages tell the story *"this app knows me specifically"* in one frame each.

### Day 15 — PWA + Demo Mode + Deploy
- [ ] Add `next-pwa`: the app installs on your phone home screen
- [ ] Build **demo mode**: a fake user with realistic synthetic data so anyone can click around without a WHOOP. (Recruiters don't have WHOOPs!)
- [ ] Push notification at 9 PM: *"Tomorrow's forecast is 54. Sleep 8h to lift it to 63."*
- [ ] Final deploys: frontend to Vercel, backend to Railway
- [ ] Write a clean README for the GitHub repo
- [ ] Record a 60-90 second Loom walkthrough showing one real, surprising insight from your own data

**Friday test:** send the live link to a friend. They install it on their phone, click through demo mode, get it in under a minute.

---

## Every Single Day (15 seconds)

The **only** thing you have to do daily is:

1. Open the app on your phone in the morning (or evening)
2. Tap through the check-in: alcohol, stress slider, late meal yes/no, sick yes/no, traveling yes/no
3. Done

The model needs your data. No data → no model.

**Until day 60**, label every insight in the UI as *"early estimate"* with confidence intervals. Be honest. Recruiters respect this. Coach doesn't do this.

---

## When You Get Stuck

| Problem | What to do |
|---|---|
| Webhook isn't firing | Check WHOOP developer dashboard; the daily 4 AM cron is your safety net anyway |
| Model R² is low (<0.2) | You probably have <30 days of data. Wait. Check back in 2 weeks. |
| SHAP values don't sum to prediction | Your explainer was built on the wrong reference data. Re-fit `LinearExplainer` on the *current* model. |
| Inverse planner returns silly recommendations (10h sleep + max strain) | Tighten the box constraints. Real bodies have correlated features; the model doesn't know that. |
| Render is slow / serverless cold start | That's fine for a portfolio project. Don't optimize until you've shipped. |

---

## Three Things You're NOT Allowed to Say in the App

These come from PRD §13 (Risks & Honest Caveats). Break these and recruiters will ding you:

1. ❌ *"Alcohol costs you 11 points."* ✅ *"Days you logged alcohol, the model predicted 11 points lower."*
2. ❌ *"You should sleep more."* ✅ *"Days with longer sleep had higher predicted recovery."*
3. ❌ *"Alcohol is bad for your heart."* ✅ Never make medical claims. Ever.

This honesty is a **feature, not a flaw**. WHOOP Coach overclaims; Recovery Debt doesn't. Make a screenshot of this side-by-side comparison for your portfolio.

---

## What Done Looks Like (the demo for recruiters)

When someone clicks your live link, in under 90 seconds they should:

1. ✅ See your live recovery chart
2. ✅ Open today's "receipt" — the SHAP breakdown with real numbers
3. ✅ Try the what-if simulator and watch the cascade
4. ✅ Type a target into the inverse planner and see a real plan come back
5. ✅ Open the wallet and see cumulative attribution over months
6. ✅ Open the profile and see *"this user is more sensitive to alcohol than to stress"*
7. ✅ Install the PWA on their phone

If they can do all 7 without you explaining anything, you've won.

---

## Source Documents

- `Recovery_Debt_PRD.md` — the full design spec
- `docs/Recovery_Debt_Project_Plan.pdf` — the original product brief
- `docs/Recovery_Debt_Data_Model_and_ML.pdf` — DB schema + ML pseudocode
- `docs/transcripts/itemized_receipt.txt`, `bank_account.txt` — the brand voice / metaphors

When in doubt, the PRD is the contract. This plan is the daily checklist.
