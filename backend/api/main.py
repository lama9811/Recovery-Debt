import logging
from contextlib import asynccontextmanager

from dotenv import load_dotenv

# Load `backend/.env` for local dev; on Railway/production there is no .env
# file and the platform injects env vars directly, so this is a no-op.
load_dotenv()

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from api import checkin, data, push, webhooks, whoop  # noqa: E402
from db.client import close_pool, open_pool  # noqa: E402

logger = logging.getLogger("recovery_debt")
logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Open the DB pool on startup, but never let a DB problem stop the app from
    # booting — if Supabase is unreachable or creds are wrong, /health still
    # has to come back 200 so the platform's healthcheck can pass and we can
    # actually read the logs to diagnose. Endpoints that need the pool will
    # fail at request time via get_pool().
    pool_opened = False
    try:
        await open_pool()
        pool_opened = True
        logger.info("DB pool opened")
    except Exception as exc:
        # Print as well as log so the failure shows up even if uvicorn's
        # log config silences our `recovery_debt` logger. The traceback is
        # the single most useful diagnostic when production /health-200s
        # but every DB endpoint 500s.
        import traceback

        print("DB pool open failed:", repr(exc), flush=True)
        traceback.print_exc()
        logger.exception("DB pool open failed — continuing without DB")
    try:
        yield
    finally:
        if pool_opened:
            await close_pool()


app = FastAPI(title="Recovery Debt API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(whoop.router)
app.include_router(webhooks.router)
app.include_router(data.router)
app.include_router(checkin.router)
app.include_router(push.router)


@app.get("/health")
async def health() -> dict[str, bool]:
    return {"ok": True}


@app.get("/health/db")
async def health_db() -> dict[str, object]:
    """Deep health check — proves the pool actually opened and can SELECT 1.
    Use this after a deploy to bisect 'app booted but DB is dead' issues."""
    from db.client import get_pool

    try:
        pool = get_pool()
    except RuntimeError as exc:
        return {"ok": False, "stage": "pool", "error": str(exc)}
    try:
        async with pool.acquire() as conn:
            v = await conn.fetchval("SELECT 1")
        return {"ok": v == 1, "stage": "query"}
    except Exception as exc:
        return {"ok": False, "stage": "query", "error": repr(exc)}
