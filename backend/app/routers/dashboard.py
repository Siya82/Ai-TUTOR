"""
Teacher Dashboard API – provides aggregated learner data.

RECOVERY NOTE: reconstructed verbatim from a read performed on 2026-08-26.
This router was found in the codebase but is not documented in any ADR or
BUILD_LOG entry — reconstructed from source only. Per later project memory,
import crashes, a SQLAlchemy cast bug, an N+1 query, and a topic-filter bug
were found and fixed in this module/its service after this snapshot — those
fixes are NOT reflected below. It also had no authentication on its
endpoints as of this snapshot; confirm whether that was added later.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.core.database import get_db
from app.models import Learner, Topic, Attempt, Question
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


@router.get("/")
async def dashboard_overview(
    db: AsyncSession = Depends(get_db)
) -> DashboardOverviewResponse:
    """Overview of all learners: names, grades, total attempts, accuracy."""
    data = await get_dashboard_summary(db)
    return DashboardOverviewResponse(**data)


@router.get("/learners/{learner_id}")
async def learner_detail(
    learner_id: UUID,
    topic_id: Optional[UUID] = Query(None),
    db: AsyncSession = Depends(get_db)
) -> LearnerDetailResponse:
    """Detailed view for a specific learner, including mastery and risk."""
    data = await get_dashboard_summary(db, learner_id, topic_id)
    if "error" in data:
        raise HTTPException(status_code=404, detail=data["error"])
    return LearnerDetailResponse(**data)


@router.get("/learners/{learner_id}/mastery")
async def learner_mastery(
    learner_id: UUID,
    topic_id: Optional[UUID] = Query(None),
    db: AsyncSession = Depends(get_db)
) -> LearnerMasteryResponse:
    """Mastery summary for a learner: accuracy per topic, misconceptions."""
    # Verify learner exists
    learner = await db.get(Learner, learner_id)
    if not learner:
        raise HTTPException(status_code=404, detail="Learner not found")
    data = await get_learner_mastery(db, learner_id, topic_id)
    return LearnerMasteryResponse(**data)


@router.get("/learners/{learner_id}/risk")
async def learner_risk(
    learner_id: UUID,
    topic_id: UUID,
    db: AsyncSession = Depends(get_db)
) -> RiskAssessmentResponse:
    """Risk assessment for a specific learner on a specific topic."""
    learner = await db.get(Learner, learner_id)
    if not learner:
        raise HTTPException(status_code=404, detail="Learner not found")
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
