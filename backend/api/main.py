from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api import whoop
from db.client import close_pool, open_pool


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Open the DB pool lazily so `python -c "import api.main"` still works
    # without DATABASE_URL set (useful in CI / quick smoke tests).
    try:
        await open_pool()
    except RuntimeError:
        pass
    yield
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
