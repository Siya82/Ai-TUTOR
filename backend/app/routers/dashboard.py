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

UPDATED 17 Nov 2026 (ADR-031, school roles and scoping): school_id
scoping is no longer enough -- every endpoint now resolves the caller's
StaffScope (app/services/school_scope.py). A learner the caller can't
see academically is an honest 404 (same posture as the cross-school 404
before), and every response only includes subjects the caller may see
for that learner.
"""



from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.core.database import get_db
from app.core.security import get_current_staff_scope
from app.models import Learner, Topic, Attempt, Question
from app.services.dashboard import (
    get_dashboard_summary,
    get_learner_mastery,
    get_learner_risk_assessment,
    get_class_progress,
)
from app.services.school_scope import ALL_SUBJECTS, StaffScope
from app.schemas.dashboard import (
    DashboardOverviewResponse,
    LearnerDetailResponse,
    LearnerMasteryResponse,
    RiskAssessmentResponse,
    ClassProgressResponse,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


async def _visible_learner(db: AsyncSession, learner_id: UUID, scope: StaffScope) -> tuple[Learner, Optional[set]]:
    """
    Returns (learner, subject_ids) where subject_ids is None for "all
    subjects". 404 -- not 403 -- when the caller can't see this learner,
    so the endpoint never confirms a learner exists outside their scope.
    """
    if learner_id not in scope.academic_learner_ids():
        raise HTTPException(status_code=404, detail="Learner not found")
    learner = await db.get(Learner, learner_id)
    if not learner:
        raise HTTPException(status_code=404, detail="Learner not found")
    subjects = scope.subjects_for(learner_id)
    return learner, (None if subjects is ALL_SUBJECTS else set(subjects))


@router.get("/")
async def dashboard_overview(
    scope: StaffScope = Depends(get_current_staff_scope),
    db: AsyncSession = Depends(get_db)
) -> DashboardOverviewResponse:
    """Overview of every learner the caller may see academically.

    Note: totals here count all of a learner's attempts; the Progress
    endpoint below is the subject-scoped view and what the UI uses."""
    data = await get_dashboard_summary(
        db, school_id=scope.school_id, learner_ids=scope.academic_learner_ids()
    )
    return DashboardOverviewResponse(**data)


@router.get("/progress")
async def class_progress(
    grade: Optional[int] = Query(None, ge=1, le=12),
    class_id: Optional[UUID] = Query(None),
    scope: StaffScope = Depends(get_current_staff_scope),
    db: AsyncSession = Depends(get_db)
) -> ClassProgressResponse:
    """NEW 17 Nov 2026 (ADR-030), scoped per ADR-031: class summary,
    per-learner risk/accuracy, and per-topic class accuracy for the
    learners and subjects the caller may see, optionally one grade or class."""
    data = await get_class_progress(db, scope, grade=grade, class_id=class_id)
    return ClassProgressResponse(**data)


@router.get("/learners/{learner_id}")
async def learner_detail(
    learner_id: UUID,
    topic_id: Optional[UUID] = Query(None),
    scope: StaffScope = Depends(get_current_staff_scope),
    db: AsyncSession = Depends(get_db)
) -> LearnerDetailResponse:
    """Detailed view for one learner: mastery, misconceptions and risk,
    limited to the subjects the caller may see for them."""
    learner, subject_ids = await _visible_learner(db, learner_id, scope)
    data = await get_dashboard_summary(db, learner.id, topic_id, subject_ids=subject_ids)
    if "error" in data:
        raise HTTPException(status_code=404, detail=data["error"])
    return LearnerDetailResponse(**data)


@router.get("/learners/{learner_id}/mastery")
async def learner_mastery(
    learner_id: UUID,
    topic_id: Optional[UUID] = Query(None),
    scope: StaffScope = Depends(get_current_staff_scope),
    db: AsyncSession = Depends(get_db)
) -> LearnerMasteryResponse:
    """Mastery summary for a learner: accuracy per topic, misconceptions."""
    learner, subject_ids = await _visible_learner(db, learner_id, scope)
    data = await get_learner_mastery(db, learner.id, topic_id, subject_ids)
    return LearnerMasteryResponse(**data)


@router.get("/learners/{learner_id}/risk")
async def learner_risk(
    learner_id: UUID,
    topic_id: UUID,
    scope: StaffScope = Depends(get_current_staff_scope),
    db: AsyncSession = Depends(get_db)
) -> RiskAssessmentResponse:
    """Risk assessment for a specific learner on a specific topic."""
    learner, subject_ids = await _visible_learner(db, learner_id, scope)
    topic = await db.get(Topic, topic_id)
    if not topic or (subject_ids is not None and topic.subject_id not in subject_ids):
        raise HTTPException(status_code=404, detail="Topic not found")

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
