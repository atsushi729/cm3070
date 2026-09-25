"""FastAPI entrypoint.

Run (from backend/, with venv active and infra up):
    uvicorn app.main:app --reload
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db import Base, engine, is_db_healthy
from app import models  # noqa: F401 — registers tables on Base.metadata

settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # create_all does not alter existing tables; use backend/scripts/*.sql for migrations.
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="Hospitality SME AI Assistant", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.api.routes import router as uc1_router  # noqa: E402
from app.api.popularity_routes import router as popularity_router  # noqa: E402
from app.api.settings_routes import router as settings_router  # noqa: E402
from app.api.sentiment_routes import router as sentiment_router  # noqa: E402

app.include_router(uc1_router)
app.include_router(popularity_router)
app.include_router(settings_router)
app.include_router(sentiment_router)


@app.get("/health")
def health() -> dict:
    try:
        with engine.connect() as conn:
            db_ok = is_db_healthy(conn)
    except Exception:
        db_ok = False
    return {"status": "ok", "env": settings.app_env, "db": db_ok}
