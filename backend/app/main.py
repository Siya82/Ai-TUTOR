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
from app.routers import subjects as subjects_router  # NEW 12 Nov 2026, multi-subject support (ADR-013)
from app.routers import attachments as attachments_router  # NEW 13 Nov 2026, student file attachments (ADR-016)
from app.routers import auth as auth_router  # NEW 14 Nov 2026, student login (ADR-017)
from app.routers import schools as schools_router  # NEW 14 Nov 2026, student login (ADR-017)
from app.routers import books as books_router  # NEW 17 Nov 2026, e-book library (ADR-032)
from app.routers import school as school_router  # NEW 17 Nov 2026, school roles and scoping (ADR-031)
from app.routers import admin as admin_router  # NEW 15 Nov 2026, teacher dashboard access + bulk student provisioning (ADR-024)
from app.routers import teach_assignments as teach_assignments_router  # NEW 15 Nov 2026, teacher assignment authoring/scoring (ADR-028)
from app.routers import learner_assignments as learner_assignments_router  # NEW 15 Nov 2026, learner assignment answering (ADR-028)

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
app.include_router(subjects_router.router, tags=["subjects"])  # NEW 12 Nov 2026, multi-subject support (ADR-013)
app.include_router(attachments_router.router, tags=["attachments"])  # NEW 13 Nov 2026, student file attachments (ADR-016)
app.include_router(auth_router.router, tags=["auth"])  # NEW 14 Nov 2026, student login (ADR-017)
app.include_router(schools_router.router, tags=["schools"])  # NEW 14 Nov 2026, student login (ADR-017)
app.include_router(books_router.router, tags=["books"])  # NEW 17 Nov 2026 (ADR-032)
app.include_router(school_router.router, tags=["school"])  # NEW 17 Nov 2026 (ADR-031)
app.include_router(admin_router.router, tags=["admin"])  # NEW 15 Nov 2026, teacher dashboard access + bulk student provisioning (ADR-024)
app.include_router(teach_assignments_router.router, tags=["assignments"])  # NEW 15 Nov 2026, teacher assignment authoring/scoring (ADR-028)
app.include_router(learner_assignments_router.router, tags=["assignments"])  # NEW 15 Nov 2026, learner assignment answering (ADR-028)


@app.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)) -> dict:
    """Confirms the API is up and can reach the database."""
    await db.execute(text("SELECT 1"))
    return {"status": "ok", "environment": settings.environment}

app.include_router(dashboard_router.router, prefix="/api/v1", tags=["dashboard"])
