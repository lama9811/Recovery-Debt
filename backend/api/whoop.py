"""WHOOP OAuth 2.0 — connect + callback.

Flow:
  1. GET /api/whoop/connect → redirect user to WHOOP authorize URL with a CSRF
     `state` token stored in an HttpOnly cookie.
  2. WHOOP redirects to GET /api/whoop/callback?code&state.
  3. We verify state cookie, exchange code for tokens, fetch the user's WHOOP
     profile, upsert `users` + `whoop_tokens`, schedule a 6-month backfill
     in the background, then redirect to FRONTEND_URL.

Backfill runs as a FastAPI BackgroundTask so the user gets their dashboard
redirect immediately while the heavier `workers/backfill.py` paged pull
happens server-side.
"""

from __future__ import annotations

import logging
import os
import secrets
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode
from uuid import UUID

import httpx
from fastapi import APIRouter, BackgroundTasks, Cookie, HTTPException
from fastapi.responses import RedirectResponse

from db.client import get_pool

logger = logging.getLogger("recovery_debt.whoop")

router = APIRouter(prefix="/api/whoop", tags=["whoop"])

WHOOP_AUTH_URL = "https://api.prod.whoop.com/oauth/oauth2/auth"
WHOOP_TOKEN_URL = "https://api.prod.whoop.com/oauth/oauth2/token"
WHOOP_PROFILE_URL = "https://api.prod.whoop.com/developer/v2/user/profile/basic"

# `offline` is what makes WHOOP return a refresh_token.
WHOOP_SCOPES = "read:recovery read:cycles read:sleep read:workout read:profile offline"

STATE_COOKIE = "whoop_oauth_state"
STATE_TTL_SECONDS = 600  # 10 minutes is plenty for an OAuth round-trip


def _frontend_url() -> str:
    return os.environ.get("FRONTEND_URL", "http://localhost:3000")


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise HTTPException(500, f"Server misconfigured: {name} not set")
    return value


@router.get("/connect")
async def connect() -> RedirectResponse:
    state = secrets.token_urlsafe(24)
    params = {
        "response_type": "code",
        "client_id": _require_env("WHOOP_CLIENT_ID"),
        "redirect_uri": _require_env("WHOOP_REDIRECT_URI"),
        "scope": WHOOP_SCOPES,
        "state": state,
    }
    response = RedirectResponse(f"{WHOOP_AUTH_URL}?{urlencode(params)}")
    # secure=True whenever the redirect URI is HTTPS (i.e. prod). On localhost
    # we fall back to insecure cookies so dev keeps working.
    is_https = _require_env("WHOOP_REDIRECT_URI").startswith("https://")
    response.set_cookie(
        STATE_COOKIE,
        state,
        max_age=STATE_TTL_SECONDS,
        httponly=True,
        secure=is_https,
        samesite="lax",
    )
    return response


async def _backfill_after_connect(user_id: UUID) -> None:
    """Background task: pull 6 months of WHOOP data right after OAuth.

    Imported lazily so the route module doesn't drag in pandas/sklearn at
    import time. Passes the Pool (not a Connection) so backfill_user can
    acquire/release per endpoint and not hold a single connection long
    enough to time out on Supabase's pgbouncer pooler.

    Logs both start and end with `print()` (in addition to the logger) so
    Railway log search can find them even when uvicorn's log config silences
    custom loggers.
    """
    import traceback

    from workers.backfill import backfill_user

    print(f"post-connect backfill START user={user_id}", flush=True)
    pool = get_pool()
    try:
        counts = await backfill_user(pool, user_id, days=180)
        print(f"post-connect backfill OK user={user_id} counts={counts}", flush=True)
        logger.info("post-connect backfill OK user=%s counts=%s", user_id, counts)
    except Exception as exc:
        print(f"post-connect backfill FAILED user={user_id} err={exc!r}", flush=True)
        traceback.print_exc()
        logger.exception("post-connect backfill failed user=%s", user_id)


@router.get("/callback")
async def callback(
    code: str,
    state: str,
    background_tasks: BackgroundTasks,
    whoop_oauth_state: str | None = Cookie(default=None),
) -> RedirectResponse:
    if not whoop_oauth_state or not secrets.compare_digest(whoop_oauth_state, state):
        raise HTTPException(400, "Invalid OAuth state")

    client_id = _require_env("WHOOP_CLIENT_ID")
    client_secret = _require_env("WHOOP_CLIENT_SECRET")
    redirect_uri = _require_env("WHOOP_REDIRECT_URI")

    async with httpx.AsyncClient(timeout=15.0) as client:
        token_resp = await client.post(
            WHOOP_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if token_resp.status_code != 200:
            raise HTTPException(401, f"WHOOP token exchange failed: {token_resp.text}")
        tokens = token_resp.json()

        access_token = tokens["access_token"]
        refresh_token = tokens["refresh_token"]
        expires_in = int(tokens.get("expires_in", 3600))
        scope = tokens.get("scope")
        expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)

        profile_resp = await client.get(
            WHOOP_PROFILE_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if profile_resp.status_code != 200:
            raise HTTPException(502, f"WHOOP profile fetch failed: {profile_resp.text}")
        profile = profile_resp.json()

    whoop_user_id = int(profile["user_id"])
    email = profile.get("email")

    pool = get_pool()
    async with pool.acquire() as conn, conn.transaction():
        user_row = await conn.fetchrow(
            """
            INSERT INTO users (whoop_user_id, email)
            VALUES ($1, $2)
            ON CONFLICT (whoop_user_id) DO UPDATE
              SET email = EXCLUDED.email
            RETURNING id
            """,
            whoop_user_id,
            email,
        )
        await conn.execute(
            """
            INSERT INTO whoop_tokens (user_id, access_token, refresh_token, expires_at, scope)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (user_id) DO UPDATE
              SET access_token  = EXCLUDED.access_token,
                  refresh_token = EXCLUDED.refresh_token,
                  expires_at    = EXCLUDED.expires_at,
                  scope         = EXCLUDED.scope,
                  updated_at    = NOW()
            """,
            user_row["id"],
            access_token,
            refresh_token,
            expires_at,
            scope,
        )

    background_tasks.add_task(_backfill_after_connect, user_row["id"])

    redirect = RedirectResponse(f"{_frontend_url()}/?connected=1")
    redirect.delete_cookie(STATE_COOKIE)
    return redirect


@router.get("/status")
async def status() -> dict[str, int]:
    """Lightweight liveness probe — counts users with stored tokens."""
    pool = get_pool()
    async with pool.acquire() as conn:
        n = await conn.fetchval("SELECT COUNT(*) FROM whoop_tokens")
    return {"connected_users": int(n or 0)}


@router.post("/backfill")
async def backfill_now(background_tasks: BackgroundTasks) -> dict[str, str]:
    """Manually trigger a backfill for the most-recently-connected WHOOP user.

    Safety net for the auto-backfill BackgroundTask in `/callback` — if that
    task didn't run, didn't complete, or returned empty, hitting this endpoint
    re-runs `backfill_user(pool, user_id, days=180)` against the latest
    connected user.
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        user_id = await conn.fetchval(
            """
            SELECT u.id FROM users u
            JOIN whoop_tokens t ON t.user_id = u.id
            ORDER BY t.updated_at DESC
            LIMIT 1
            """
        )
    if not user_id:
        raise HTTPException(404, "No WHOOP-connected user found")
    background_tasks.add_task(_backfill_after_connect, user_id)
    return {"ok": "scheduled", "user_id": str(user_id)}


@router.post("/backfill-sync")
async def backfill_sync() -> dict[str, object]:
    """Diagnostic: run backfill synchronously and return the result/traceback.

    Used to debug `/backfill` (which schedules a BackgroundTask whose errors
    only surface in Railway logs). This endpoint blocks the request until
    backfill finishes, then returns either {ok: True, counts: ...} or
    {ok: False, error: ..., traceback: ...} so we can see exactly what's
    failing in production from outside the Railway log UI. Slow (~30-60 sec).
    """
    import traceback

    from workers.backfill import backfill_user

    pool = get_pool()
    async with pool.acquire() as conn:
        user_id = await conn.fetchval(
            """
            SELECT u.id FROM users u
            JOIN whoop_tokens t ON t.user_id = u.id
            ORDER BY t.updated_at DESC
            LIMIT 1
            """
        )
    if not user_id:
        raise HTTPException(404, "No WHOOP-connected user found")
    try:
        counts = await backfill_user(pool, user_id, days=180)
        return {"ok": True, "user_id": str(user_id), "counts": counts}
    except Exception as exc:
        return {
            "ok": False,
            "user_id": str(user_id),
            "error": repr(exc),
            "traceback": traceback.format_exc(),
        }
