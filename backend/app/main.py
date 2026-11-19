"""
FastAPI application entrypoint.

RECOVERY NOTE: reconstructed verbatim from a read performed on 2026-08-26.
Per later project memory, auth routers and possibly a quiz-engine router
were added after this snapshot — not reflected below. See REBUILD_SPEC.md.
"""

import logging
import time

import anthropic
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

from app.core.config import settings
from app.core.database import get_db
from app.routers import tutor as tutor_router
from app.routers import dashboard as dashboard_router
from app.routers import topics as topics_router
from app.routers import subjects as subjects_router  # NEW 12 Nov 2026, multi-subject support (ADR-013)
from app.routers import attachments as attachments_router  # NEW 13 Nov 2026, student file attachments (ADR-016)
from app.routers import auth as auth_router  # NEW 14 Nov 2026, student login (ADR-017)
from app.routers import schools as schools_router  # NEW 14 Nov 2026, student login (ADR-017)
from app.routers import books as books_router  # NEW 17 Nov 2026, e-book library (ADR-032)
from app.routers import school as school_router  # NEW 17 Nov 2026, school roles and scoping (ADR-031)
from app.routers import admin as admin_router  # NEW 15 Nov 2026, teacher dashboard access + bulk student provisioning (ADR-024)
from app.routers import teach_assignments as teach_assignments_router  # NEW 15 Nov 2026, teacher assignment authoring/scoring (ADR-028)
from app.routers import learner_assignments as learner_assignments_router  # NEW 15 Nov 2026, learner assignment answering (ADR-028)
from app.routers import teacher_today as teacher_today_router  # NEW 19 Nov 2026 (ADR-036)
from app.routers import privacy as privacy_router  # NEW 19 Nov 2026 (ADR-037)
from app.routers import connect as connect_router  # NEW 19 Nov 2026 (ADR-038)

app = FastAPI(
    title="AI CAPS Tutor — Pilot API",
    description="Grade 10 Mathematics AI tutor pilot",
    version="0.1.0",
)

# NEW 17 Nov 2026 (code review #10): the backend had no logging at all, so
# a problem during a live test left no trace. One line per request (method,
# path, status, time -- never bodies, which hold learners' messages) plus
# full tracebacks for errors.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("thutora")


@app.middleware("http")
async def log_requests(request: Request, call_next):
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        log.exception("Unhandled error on %s %s", request.method, request.url.path)
        raise
    elapsed_ms = (time.perf_counter() - started) * 1000
    level = logging.WARNING if response.status_code >= 500 else logging.INFO
    log.log(level, "%s %s -> %s (%.0f ms)", request.method, request.url.path, response.status_code, elapsed_ms)
    return response


@app.exception_handler(anthropic.APIError)
async def claude_unavailable(request: Request, exc: anthropic.APIError) -> JSONResponse:
    """
    Claude timed out, was overloaded, or rejected the request. The learner
    gets a plain message and can retry (the chat puts their question back);
    the details go to the log.
    """
    log.error("Claude API error on %s: %s: %s", request.url.path, type(exc).__name__, exc)
    return JSONResponse(
        status_code=503,
        content={"detail": "THUTOra couldn't reach its AI tutor just now. Please try again in a moment."},
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(teacher_today_router.router)
app.include_router(privacy_router.router)
app.include_router(connect_router.router)
app.include_router(tutor_router.router, prefix="/tutor", tags=["tutor"])
app.include_router(topics_router.router, tags=["topics"])  # NEW 8 Nov 2026, step 7
# REMOVED 17 Nov 2026 (code review #1): GET /learners/ listed every learner in every
# school without a login. It predated auth and nothing used it any more.
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
