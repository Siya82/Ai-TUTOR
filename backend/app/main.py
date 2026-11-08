"""
FastAPI application entrypoint.

RECOVERY NOTE: reconstructed verbatim from a read performed on 2026-08-26.
Per later project memory, auth routers and possibly a quiz-engine router
were added after this snapshot — not reflected below. See REBUILD_SPEC.md.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

from app.core.config import settings
from app.core.database import get_db
from app.routers import tutor as tutor_router
from app.routers import dashboard as dashboard_router
from app.routers import topics as topics_router
from app.routers import learners as learners_router

app = FastAPI(
    title="AI CAPS Tutor — Pilot API",
    description="Grade 10 Mathematics AI tutor pilot",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tutor_router.router, prefix="/tutor", tags=["tutor"])
app.include_router(topics_router.router, tags=["topics"])  # NEW 8 Nov 2026, step 7
app.include_router(learners_router.router, tags=["learners"])  # NEW 8 Nov 2026, step 7


@app.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)) -> dict:
    """Confirms the API is up and can reach the database."""
    await db.execute(text("SELECT 1"))
    return {"status": "ok", "environment": settings.environment}

app.include_router(dashboard_router.router, prefix="/api/v1", tags=["dashboard"])
