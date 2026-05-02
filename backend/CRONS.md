# Railway cron setup

Railway crons are configured per-service through the dashboard, not in
`railway.json`. Once the backend is deployed, add two crons that share the
same image and env vars as the web service:

| When | Command | Why |
|---|---|---|
| `0 4 * * *` | `python -m workers.safety_net` | Re-pulls the last 3 days of WHOOP data for every connected user. Catches dropped webhooks. |
| `30 4 * * *` | `python -m workers.train_now` | Retrains the Ridge model on the freshly-updated data, writes tomorrow's prediction + SHAP. Runs 30 minutes after the safety net so it sees the new rows. |
| `0 21 * * *` | `python -m workers.notify_evening` | Sends the 9 PM Web Push: "Tomorrow's predicted recovery is X". No-ops if `VAPID_PRIVATE_KEY` / `VAPID_SUBJECT` are unset. |

**Steps in the Railway dashboard**

1. Open the project → `recovery-debt-production` service.
2. Settings → **Add cron schedule**.
3. Schedule: `0 4 * * *`, command: `python -m workers.safety_net`.
4. Repeat for `30 4 * * *` / `python -m workers.train_now`.
5. Repeat for `0 21 * * *` / `python -m workers.notify_evening` (only after VAPID env vars are set — see `.env.example`).

Railway uses the deployment's TZ (UTC by default). To run at 4 AM
**America/New_York**, schedule `0 8 * * *` and `30 8 * * *` instead, or set
`TZ=America/New_York` in the service env vars.

**Verifying**

The two scripts are designed to be safe to re-run on demand from anywhere:

```bash
# Locally, with .env loaded:
python -m workers.safety_net       # idempotent — UNIQUE (user_id, day) handles re-pulls
python -m workers.train_now        # writes a new model artifact + prediction every run
python -m workers.notify_evening   # no-op without VAPID; otherwise pushes once per subscription
```

If a cron fails, Railway logs the stderr; all three scripts use the standard
`logging` module so the failure context is captured.

**Generating a VAPID keypair**

The evening-notification worker needs a VAPID keypair. Generate once and
store the public key in the frontend env (`NEXT_PUBLIC_VAPID_PUBLIC_KEY`)
and the private key in the backend env (`VAPID_PRIVATE_KEY`):

```bash
pip install py-vapid
vapid --gen                      # writes private_key.pem + public_key.pem
vapid --applicationServerKey     # prints the URL-safe base64 public key
```

Set `VAPID_SUBJECT=mailto:you@example.com` so push services can reach you
on bounce. Apply `db/migrations/001_push_subscriptions.sql` to the database
before scheduling the cron.
