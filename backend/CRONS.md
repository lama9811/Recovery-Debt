# Railway cron setup

Railway crons are configured per-service through the dashboard, not in
`railway.json`. Once the backend is deployed, add two crons that share the
same image and env vars as the web service:

| When | Command | Why |
|---|---|---|
| `0 4 * * *` | `python -m workers.safety_net` | Re-pulls the last 3 days of WHOOP data for every connected user. Catches dropped webhooks. |
| `30 4 * * *` | `python -m workers.train_now` | Retrains the Ridge model on the freshly-updated data, writes tomorrow's prediction + SHAP. Runs 30 minutes after the safety net so it sees the new rows. |

**Steps in the Railway dashboard**

1. Open the project → `recovery-debt-production` service.
2. Settings → **Add cron schedule**.
3. Schedule: `0 4 * * *`, command: `python -m workers.safety_net`.
4. Repeat for `30 4 * * *` / `python -m workers.train_now`.

Railway uses the deployment's TZ (UTC by default). To run at 4 AM
**America/New_York**, schedule `0 8 * * *` and `30 8 * * *` instead, or set
`TZ=America/New_York` in the service env vars.

**Verifying**

The two scripts are designed to be safe to re-run on demand from anywhere:

```bash
# Locally, with .env loaded:
python -m workers.safety_net   # idempotent — UNIQUE (user_id, day) handles re-pulls
python -m workers.train_now    # writes a new model artifact + prediction every run
```

If a cron fails, Railway logs the stderr; both scripts use the standard
`logging` module so the failure context is captured.
