from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth.router import router as auth_router
from app.config import settings
from app.database import engine
from app.routers.content import router as content_router


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
