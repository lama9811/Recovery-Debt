"""WHOOP OAuth 2.0 — connect + callback.

Flow:
  1. GET /api/whoop/connect → redirect user to WHOOP authorize URL with a CSRF
     `state` token stored in an HttpOnly cookie.
  2. WHOOP redirects to GET /api/whoop/callback?code&state.
  3. We verify state cookie, exchange code for tokens, fetch the user's WHOOP
     profile, upsert `users` + `whoop_tokens`, then redirect to FRONTEND_URL.

Token refresh + backfill come on Day 3; this file only covers the OAuth dance.
"""

from __future__ import annotations

import os
import secrets
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Cookie, HTTPException
from fastapi.responses import RedirectResponse

from db.client import get_pool

router = APIRouter(prefix="/api/whoop", tags=["whoop"])

WHOOP_AUTH_URL = "https://api.prod.whoop.com/oauth/oauth2/auth"
WHOOP_TOKEN_URL = "https://api.prod.whoop.com/oauth/oauth2/token"
WHOOP_PROFILE_URL = "https://api.prod.whoop.com/developer/v1/user/profile/basic"

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
    response.set_cookie(
        STATE_COOKIE,
        state,
        max_age=STATE_TTL_SECONDS,
        httponly=True,
        secure=False,  # local dev is http; production reverse proxy upgrades this
        samesite="lax",
    )
    return response


@router.get("/callback")
async def callback(
    code: str,
    state: str,
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
