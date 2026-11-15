"""
Teacher Dashboard API – provides aggregated learner data.

RECOVERY NOTE: reconstructed verbatim from a read performed on 2026-08-26.
This router was found in the codebase but is not documented in any ADR or
BUILD_LOG entry — reconstructed from source only. Per later project memory,
import crashes, a SQLAlchemy cast bug, an N+1 query, and a topic-filter bug
were found and fixed in this module/its service after this snapshot — those
fixes are NOT reflected below.

FIX 15 Nov 2026 (ADR-024, teacher dashboard access + bulk student
provisioning): this router had no authentication at all until now --
closing a gap this project's own report/BUILD_LOG flagged as open since
the very first report (26 Aug 2026). Every endpoint below now requires
a teacher-role User (get_current_teacher), and every learner-scoped
endpoint additionally confirms that learner belongs to a User in the
teacher's OWN school via _assert_same_school -- a teacher at School A
getting a 404 for a real learner_id that belongs to School B is the
intended, privacy-preserving behaviour, not a bug.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.core.database import get_db
from app.core.security import get_current_teacher
from app.models import Learner, Topic, Attempt, Question, User
from app.services.dashboard import (
    get_dashboard_summary,
    get_learner_mastery,
    get_learner_risk_assessment
)
from app.schemas.dashboard import (
    DashboardOverviewResponse,
    LearnerDetailResponse,
    LearnerMasteryResponse,
    RiskAssessmentResponse
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


async def _assert_same_school(db: AsyncSession, learner: Learner, teacher: User) -> None:
    """
    NEW 15 Nov 2026 (ADR-024). Confirms `learner` belongs to a User in
    the authenticated teacher's own school before any data about them
    is returned. A Learner with no linked User at all (old dev data
    seeded before ADR-017's student-login work existed) has no school
    to scope it to, so it's treated the same as "not this teacher's" --
    a 404, not a crash and not a silent bypass.
    """
    if learner.user_id is None:
        raise HTTPException(status_code=404, detail="Learner not found")
    learner_user = await db.get(User, learner.user_id)
    if learner_user is None or learner_user.school_id != teacher.school_id:
        raise HTTPException(status_code=404, detail="Learner not found")


@router.get("/")
async def dashboard_overview(
    teacher: User = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db)
) -> DashboardOverviewResponse:
    """Overview of every learner IN THE TEACHER'S OWN SCHOOL: names, grades, total attempts, accuracy.

    FIX 15 Nov 2026 (ADR-024): previously listed every Learner in the
    database regardless of school -- now scoped via school_id, since
    this endpoint is no longer unauthenticated."""
    data = await get_dashboard_summary(db, school_id=teacher.school_id)
    return DashboardOverviewResponse(**data)


@router.get("/learners/{learner_id}")
async def learner_detail(
    learner_id: UUID,
    topic_id: Optional[UUID] = Query(None),
    teacher: User = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db)
) -> LearnerDetailResponse:
    """Detailed view for a specific learner, including mastery and risk."""
    learner = await db.get(Learner, learner_id)
    if not learner:
        raise HTTPException(status_code=404, detail="Learner not found")
    await _assert_same_school(db, learner, teacher)
    data = await get_dashboard_summary(db, learner_id, topic_id)
    if "error" in data:
        raise HTTPException(status_code=404, detail=data["error"])
    return LearnerDetailResponse(**data)


@router.get("/learners/{learner_id}/mastery")
async def learner_mastery(
    learner_id: UUID,
    topic_id: Optional[UUID] = Query(None),
    teacher: User = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db)
) -> LearnerMasteryResponse:
    """Mastery summary for a learner: accuracy per topic, misconceptions."""
    # Verify learner exists AND belongs to this teacher's school
    learner = await db.get(Learner, learner_id)
    if not learner:
        raise HTTPException(status_code=404, detail="Learner not found")
    await _assert_same_school(db, learner, teacher)
    data = await get_learner_mastery(db, learner_id, topic_id)
    return LearnerMasteryResponse(**data)


@router.get("/learners/{learner_id}/risk")
async def learner_risk(
    learner_id: UUID,
    topic_id: UUID,
    teacher: User = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db)
) -> RiskAssessmentResponse:
    """Risk assessment for a specific learner on a specific topic."""
    learner = await db.get(Learner, learner_id)
    if not learner:
        raise HTTPException(status_code=404, detail="Learner not found")
    await _assert_same_school(db, learner, teacher)
    topic = await db.get(Topic, topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    # Fetch prerequisite attempts if any
    prereq_attempts = None
    if topic.prerequisite_id:
        stmt = (
            select(Attempt)
            .join(Question, Attempt.question_id == Question.id)
            .where(Attempt.learner_id == learner_id)
            .where(Question.topic_id == topic.prerequisite_id)
            .where(Attempt.is_correct.isnot(None))
        )
        result = await db.execute(stmt)
        prereq_attempts = result.scalars().all()

    risk_data = await get_learner_risk_assessment(db, learner, topic, prereq_attempts)
    return RiskAssessmentResponse(**risk_data)
