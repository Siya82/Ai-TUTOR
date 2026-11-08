"""
Dashboard service – aggregates learner mastery, risk, and performance data
for teacher dashboards.

RECOVERY NOTE: reconstructed verbatim from a read performed on 2026-08-26.
Per later project memory, this module had an import crash, a SQLAlchemy
cast bug, an N+1 query, and a topic-filter bug fixed after this snapshot —
not reflected below. Re-review carefully against real test data on rebuild
rather than trusting this copy blindly.
"""

from typing import List, Dict, Optional
from uuid import UUID
from sqlalchemy import select, func, Float
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Learner, Attempt, Question, Topic, Subject
)
from app.services.risk_assessment import assess_risk, RiskLevel


async def get_learner_mastery(
    db: AsyncSession,
    learner_id: UUID,
    topic_id: Optional[UUID] = None
) -> Dict:
    """
    Returns mastery summary for a learner:
    - Overall accuracy per topic (recent window)
    - Number of attempts
    - Last attempt date
    - Identified misconceptions (from AI feedback)
    """
    # Build query for attempts with topic info
    stmt = (
        select(
            Topic.id.label("topic_id"),
            Topic.name.label("topic_name"),
            func.count(Attempt.id).label("attempt_count"),
            func.avg(Attempt.is_correct.cast(Float)).label("accuracy"),
            func.max(Attempt.created_at).label("last_attempt")
        )
        .join(Question, Attempt.question_id == Question.id)
        .join(Topic, Question.topic_id == Topic.id)
        .where(Attempt.learner_id == learner_id)
        .where(Attempt.is_correct.isnot(None))
        .group_by(Topic.id, Topic.name)
        .order_by(Topic.name)
    )
    if topic_id:
        stmt = stmt.where(Topic.id == topic_id)

    result = await db.execute(stmt)
    rows = result.all()

    # Fetch recent incorrect attempts with AI feedback to extract misconceptions.
    # Respect the topic_id filter so results stay consistent with the mastery
    # rows returned above, and limit directly in the query.
    mis_stmt = (
        select(Attempt, Question.text, Topic.name)
        .join(Question, Attempt.question_id == Question.id)
        .join(Topic, Question.topic_id == Topic.id)
        .where(Attempt.learner_id == learner_id)
        .where(Attempt.is_correct == False)
        .where(Attempt.ai_feedback.isnot(None))
    )
    if topic_id:
        mis_stmt = mis_stmt.where(Topic.id == topic_id)
    mis_stmt = mis_stmt.order_by(Attempt.created_at.desc()).limit(5)

    mis_result = await db.execute(mis_stmt)
    misconceptions = []
    for attempt, qtext, tname in mis_result:
        misconceptions.append({
            "topic": tname,
            "question": qtext[:100] + "...",
            "feedback": attempt.ai_feedback[:200] + "..."
        })

    # Build response
    topics_mastery = []
    for row in rows:
        topics_mastery.append({
            "topic_id": str(row.topic_id),
            "topic_name": row.topic_name,
            "attempt_count": row.attempt_count,
            "accuracy": round(row.accuracy, 2) if row.accuracy is not None else None,
            "last_attempt": row.last_attempt.isoformat() if row.last_attempt else None
        })

    return {
        "learner_id": str(learner_id),
        "topics": topics_mastery,
        "recent_misconceptions": misconceptions
    }


async def get_learner_risk_assessment(
    db: AsyncSession,
    learner: Learner,
    topic: Topic,
    prerequisite_attempts: Optional[List[Attempt]] = None
) -> Dict:
    """
    Wraps the risk_assessment service with data fetch.
    """
    # Get attempts for this learner on this topic
    stmt = (
        select(Attempt)
        .join(Question, Attempt.question_id == Question.id)
        .where(Attempt.learner_id == learner.id)
        .where(Question.topic_id == topic.id)
        .where(Attempt.is_correct.isnot(None))
    )
    result = await db.execute(stmt)
    learner_attempts = result.scalars().all()

    risk = assess_risk(
        learner_attempts=learner_attempts,
        topic=topic,
        prerequisite_attempts=prerequisite_attempts
    )
    return {
        "learner_id": str(learner.id),
        "topic_id": str(topic.id),
        "topic_name": topic.name,
        "risk_level": risk.level.value,
        "factors": risk.factors,
        "interventions": risk.recommended_interventions
    }


async def get_dashboard_summary(
    db: AsyncSession,
    learner_id: Optional[UUID] = None,
    topic_id: Optional[UUID] = None
) -> Dict:
    """
    Overall dashboard summary:
    - List of learners (if no learner_id) with basic stats
    - Or detailed summary for a specific learner
    """
    if learner_id:
        # Detailed view for one learner
        learner = await db.get(Learner, learner_id)
        if not learner:
            return {"error": "Learner not found"}

        mastery = await get_learner_mastery(db, learner_id, topic_id)

        # Get all topics for this learner's grade to compute risk for each
        topics_stmt = select(Topic).where(Topic.subject_id.in_(
            select(Subject.id).where(Subject.grade == learner.grade)
        ))
        topics_result = await db.execute(topics_stmt)
        topics = topics_result.scalars().all()

        risks = []
        for t in topics:
            # Get prerequisite attempts (if any)
            prereq_attempts = None
            if t.prerequisite_id:
                prereq_stmt = (
                    select(Attempt)
                    .join(Question, Attempt.question_id == Question.id)
                    .where(Attempt.learner_id == learner_id)
                    .where(Question.topic_id == t.prerequisite_id)
                    .where(Attempt.is_correct.isnot(None))
                )
                prereq_result = await db.execute(prereq_stmt)
                prereq_attempts = prereq_result.scalars().all()
            risk = await get_learner_risk_assessment(db, learner, t, prereq_attempts)
            risks.append(risk)

        return {
            "learner": {
                "id": str(learner.id),
                "name": learner.display_name,
                "grade": learner.grade
            },
            "mastery": mastery,
            "risk_assessments": risks
        }
    else:
        # Overview: list of all learners with their stats and last activity.
        # Computed with a single aggregated query (subquery + outer join)
        # instead of looping per-learner, to avoid N+1 round-trips.
        stats_subq = (
            select(
                Attempt.learner_id.label("learner_id"),
                func.count(Attempt.id).label("total_attempts"),
                func.avg(Attempt.is_correct.cast(Float)).label("overall_accuracy"),
                func.max(Attempt.created_at).label("last_activity")
            )
            .where(Attempt.is_correct.isnot(None))
            .group_by(Attempt.learner_id)
            .subquery()
        )

        stmt = (
            select(
                Learner,
                stats_subq.c.total_attempts,
                stats_subq.c.overall_accuracy,
                stats_subq.c.last_activity
            )
            .outerjoin(stats_subq, Learner.id == stats_subq.c.learner_id)
            .order_by(Learner.display_name)
        )
        result = await db.execute(stmt)
        rows = result.all()

        learner_list = []
        for learner, total_attempts, accuracy, last_activity in rows:
            learner_list.append({
                "id": str(learner.id),
                "name": learner.display_name,
                "grade": learner.grade,
                "total_attempts": total_attempts or 0,
                "overall_accuracy": round(accuracy, 2) if accuracy is not None else None,
                "last_activity": last_activity.isoformat() if last_activity else None
            })

        return {
            "learners": learner_list,
            "total_learners": len(learner_list)
        }
