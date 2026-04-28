import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api import whoop
from db.client import close_pool, open_pool

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
    except Exception:
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


@app.get("/health")
async def health() -> dict[str, bool]:
    return {"ok": True}
