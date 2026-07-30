from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth.router import router as auth_router
from app.config import settings
from app.database import engine
from app.routers.analytics import router as analytics_router
from app.routers.content import router as content_router
from app.routers.evidence import router as evidence_router
from app.routers.gate import router as gate_router
from app.routers.journal import router as journal_router
from app.routers.learning import router as learning_router
from app.routers.missed_trades import router as missed_trades_router
from app.routers.planner import router as planner_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()


app = FastAPI(
    title="Neurospect Learn API",
    description="Learning Platform backend — course content, progress, journal, gate",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — frontend SPA on a different origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health check
@app.get("/health", tags=["system"])
async def health():
    return {"status": "ok"}


# Auth
app.include_router(auth_router)

# Content API (course corpus — ingested wiki markdown)
app.include_router(content_router)

# Evidence API (E2 — captured evidence of the work; the ONLY way a rep is minted)
app.include_router(evidence_router)

# Learning API (progress, derived stage exit-bars, drills)
app.include_router(learning_router)

# Study-Planner API (preferences, today, calendar, regenerate, mark-item-done)
app.include_router(planner_router)

# Journal API (model-aligned backtest|live entries — the proof-of-edge write side)
app.include_router(journal_router)

# Missed-trade log (6b — the trades you did NOT take; never enters expectancy)
app.include_router(missed_trades_router)

# Analytics API (per-model expectancy, mode summary, R distribution, opportunity cost)
app.include_router(analytics_router)

# Gate API (the computed per-model "cleared to live?" verdict — non-overridable)
app.include_router(gate_router)
