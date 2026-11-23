"""
FastAPI application entrypoint.

RECOVERY NOTE: reconstructed verbatim from a read performed on 2026-08-26.
Per later project memory, auth routers and possibly a quiz-engine router
were added after this snapshot — not reflected below. See REBUILD_SPEC.md.
"""

import logging
import time
from contextlib import asynccontextmanager

import anthropic
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

from app.core.config import settings, topic_video_path
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
from app.routers import insights as insights_router  # NEW 19 Nov 2026 (ADR-039)
from app.routers import family as family_router  # NEW 19 Nov 2026 (ADR-043)
from app.routers import school_admin as school_admin_router  # NEW 19 Nov 2026 (ADR-044)
from app.routers import client_errors as client_errors_router  # NEW 20 Nov 2026 (deep scan H4)
from app.routers import support as support_router  # NEW 23 Nov 2026 (ADR-050)
from app.routers import console as console_router  # NEW 23 Nov 2026 (ADR-051)

IS_PRODUCTION = settings.environment.lower() in ("production", "prod")

# deep scan H4: refuse to start with unsafe production settings
from app.core.production import check_production_settings  # noqa: E402

check_production_settings(settings)

@asynccontextmanager
async def lifespan(_app):
    # (FastAPI's lifespan replaces the deprecated @app.on_event("startup"))
    await _report_pending_registrations()
    await _report_open_tickets()
    yield


app = FastAPI(
    lifespan=lifespan,
    title="THUTOra API",
    description="THUTOra -- CAPS-aligned AI tutor and school platform",
    version="1.0.0",
    # deep scan H4: no public API explorer in production
    docs_url=None if IS_PRODUCTION else "/docs",
    redoc_url=None if IS_PRODUCTION else "/redoc",
    openapi_url=None if IS_PRODUCTION else "/openapi.json",
)

# NEW 17 Nov 2026 (code review #10): the backend had no logging at all, so
# a problem during a live test left no trace. One line per request (method,
# path, status, time -- never bodies, which hold learners' messages) plus
# full tracebacks for errors.
if settings.log_format == "json":  # deep scan H4: Cloud Logging-friendly
    from app.core.production import configure_json_logging

    configure_json_logging()
else:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
log = logging.getLogger("thutora")

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Cache-Control": "no-store",
}


@app.middleware("http")
async def log_requests(request: Request, call_next):
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        log.exception("Unhandled error on %s %s", request.method, request.url.path)
        raise
    elapsed_ms = (time.perf_counter() - started) * 1000
    # deep scan H4: security headers on every API response; personal data
    # must never be stored by a shared proxy or the browser's disk cache
    if request.url.path.startswith("/media/"):  # ADR-049: public, cacheable videos
        response.headers["Cache-Control"] = "public, max-age=86400"
    for header, value in SECURITY_HEADERS.items():
        response.headers.setdefault(header, value)
    if IS_PRODUCTION:
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
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


# deep scan M6: Cloud Run doesn't compress responses. The Progress and Today
# lists are repetitive JSON, so gzip cuts them by roughly 90% -- most of a
# teacher's wait on a slow school connection.
app.add_middleware(GZipMiddleware, minimum_size=1024)  # skips video/* and other compressed types

app.add_middleware(
    CORSMiddleware,
    # ADR-051: the Console website is a separate origin; it can only use /console (console_guard)
    allow_origins=settings.cors_origins + (settings.console_origins if settings.console_enabled else []),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(teacher_today_router.router)
app.include_router(privacy_router.router)
app.include_router(connect_router.router)
app.include_router(insights_router.router)
app.include_router(family_router.router)
app.include_router(school_admin_router.router)
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
app.include_router(client_errors_router.router, tags=["ops"])
app.include_router(support_router.router)
app.include_router(console_router.router)

# ADR-049: topic overview videos. Curriculum content, not personal data, so
# no login is needed and browsers may cache them. Starlette serves byte
# ranges, so the video player can seek. In production they move to a
# Cloud Storage bucket (docs/RUNBOOK.md).
_videos = topic_video_path()
_videos.mkdir(parents=True, exist_ok=True)
app.mount("/media/topic-videos", StaticFiles(directory=_videos), name="topic-videos")


async def _report_pending_registrations() -> None:
    """code review 19 Nov #16: say at every start-up if schools are waiting."""
    try:
        from sqlalchemy import func, select

        from app.core.database import async_session_factory
        from app.models import SchoolRegistration

        async with async_session_factory() as db:
            pending = (
                await db.execute(
                    select(func.count()).select_from(SchoolRegistration).where(SchoolRegistration.status == "pending")
                )
            ).scalar_one()
        if pending:
            log.warning(
                "%d school registration request(s) waiting. List them with: python -m scripts.manage_registrations list",
                pending,
            )
    except Exception as exc:  # noqa: BLE001 -- never block start-up for a reminder
        log.info("Couldn't check school registrations at start-up: %s", exc)


async def _report_open_tickets() -> None:
    """ADR-050: say at every start-up if schools are waiting on support."""
    try:
        from sqlalchemy import func, select

        from app.core.database import async_session_factory
        from app.models import SupportTicket

        async with async_session_factory() as db:
            waiting = (
                await db.execute(
                    select(func.count()).select_from(SupportTicket).where(SupportTicket.status == "open")
                )
            ).scalar_one()
        if waiting:
            log.warning("%d support ticket(s) waiting for Zynora. List them with: python -m scripts.support list", waiting)
    except Exception as exc:  # noqa: BLE001 -- never block start-up for a reminder
        log.info("Couldn't check support tickets at start-up: %s", exc)
