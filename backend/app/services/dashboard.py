"""
Dashboard service – aggregates learner mastery, risk, and performance data
for teacher dashboards.

RECOVERY NOTE: reconstructed verbatim from a read performed on 2026-08-26.
Per later project memory, this module had an import crash, a SQLAlchemy
cast bug, an N+1 query, and a topic-filter bug fixed after this snapshot —
not reflected below. Re-review carefully against real test data on rebuild
rather than trusting this copy blindly.

NEW 15 Nov 2026 (ADR-024, teacher dashboard access + bulk student
provisioning): get_dashboard_summary()'s overview branch gained an
optional `school_id` filter so app/routers/dashboard.py can scope the
"list every learner" view to the authenticated teacher's own school,
now that the endpoint actually has authentication to scope by.
"""

from typing import List, Dict, Optional
from uuid import UUID
from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Learner, Attempt, Question, Topic, Subject, User, ClassMember
)
from app.services.risk_assessment import assess_risk, RiskLevel
from app.services.class_progress import (
    AttemptRow,
    LearnerRow,
    TopicRow,
    assess_learner_topics,
    summarize_class_progress,
)


# FIX 17 Nov 2026 (ADR-030): was `Attempt.is_correct.cast(Float)`, which
# PostgreSQL rejects ("cannot cast type boolean to double precision" --
# Postgres only defines boolean -> integer). Never hit live before, because
# no Attempt row existed anywhere until ADR-028's assignments wrote the
# first ones. A CASE works on every backend; AVG of it returns a Decimal,
# converted to float where it's rounded below.
_CORRECT_AS_NUMBER = case((Attempt.is_correct.is_(True), 1), else_=0)


async def get_learner_mastery(
    db: AsyncSession,
    learner_id: UUID,
    topic_id: Optional[UUID] = None,
    subject_ids: Optional[set] = None,
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
            Subject.name.label("subject_name"),
            Subject.grade.label("grade"),
            func.count(Attempt.id).label("attempt_count"),
            func.avg(_CORRECT_AS_NUMBER).label("accuracy"),
            func.max(Attempt.created_at).label("last_attempt")
        )
        .join(Question, Attempt.question_id == Question.id)
        .join(Topic, Question.topic_id == Topic.id)
        .join(Subject, Topic.subject_id == Subject.id)
        .where(Attempt.learner_id == learner_id)
        .where(Attempt.is_correct.isnot(None))
        .group_by(Topic.id, Topic.name, Subject.name, Subject.grade, Topic.order_index)
        .order_by(Subject.grade, Subject.name, Topic.order_index, Topic.name)
    )
    if topic_id:
        stmt = stmt.where(Topic.id == topic_id)
    # NEW 17 Nov 2026 (ADR-031): None = every subject (whole-school roles);
    # a set = only those subjects (a teacher's allocation, a departmental head's department).
    if subject_ids is not None:
        stmt = stmt.where(Topic.subject_id.in_(subject_ids))

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
    if subject_ids is not None:
        mis_stmt = mis_stmt.where(Topic.subject_id.in_(subject_ids))
    mis_stmt = mis_stmt.order_by(Attempt.created_at.desc()).limit(5)

    mis_result = await db.execute(mis_stmt)
    misconceptions = []
    for attempt, qtext, tname in mis_result:
        misconceptions.append({
            "topic": tname,
            "question": qtext if len(qtext) <= 100 else qtext[:100] + "...",
            "feedback": attempt.ai_feedback if len(attempt.ai_feedback) <= 200 else attempt.ai_feedback[:200] + "..."
        })

    # Build response
    topics_mastery = []
    for row in rows:
        topics_mastery.append({
            "topic_id": str(row.topic_id),
            "topic_name": row.topic_name,
            "subject_name": row.subject_name,
            "grade": row.grade,
            "attempt_count": row.attempt_count,
            "accuracy": round(float(row.accuracy), 2) if row.accuracy is not None else None,
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
    topic_id: Optional[UUID] = None,
    school_id: Optional[UUID] = None,
    subject_ids: Optional[set] = None,
    learner_ids: Optional[set] = None,
) -> Dict:
    """
    Overall dashboard summary:
    - List of learners (if no learner_id) with basic stats
    - Or detailed summary for a specific learner

    `school_id` (NEW 15 Nov 2026, ADR-024) only affects the "list every
    learner" branch below -- the single-learner branch already takes a
    specific learner_id, and the caller (app/routers/dashboard.py) is
    responsible for confirming THAT learner belongs to the requesting
    teacher's school before calling this at all, via _assert_same_school.
    """
    if learner_id:
        # Detailed view for one learner
        learner = await db.get(Learner, learner_id)
        if not learner:
            return {"error": "Learner not found"}

        mastery = await get_learner_mastery(db, learner_id, topic_id, subject_ids)

        # FIX 17 Nov 2026 (ADR-030): previously looped over EVERY topic in
        # the learner's grade with 1-2 queries per topic (N+1), and
        # assessed topics the learner had never touched (always "low",
        # pure noise). Now: one attempts query + one topics query, risk
        # computed in memory over the candidate set -- see
        # app/services/class_progress.py's module docstring.
        topics = await _load_topic_rows(db)
        attempts = await _load_attempt_rows(db, [learner.id])
        if subject_ids is not None:
            # ADR-031: only the subjects this viewer may see for this learner
            topics = {k: t for k, t in topics.items() if t.subject_id in subject_ids}
            attempts = [a for a in attempts if a.topic_id in topics]
        risks = assess_learner_topics(
            LearnerRow(id=learner.id, name=learner.display_name, grade=learner.grade),
            attempts,
            topics,
        )
        if topic_id:
            risks = [r for r in risks if r["topic_id"] == str(topic_id)]

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
                func.avg(_CORRECT_AS_NUMBER).label("overall_accuracy"),
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
        )
        # NEW 15 Nov 2026 (ADR-024): scoping join is only added when a
        # school_id filter was actually requested, so this query's shape
        # (and its existing test coverage, if any calls it with no
        # school_id) is unchanged for every other caller.
        if school_id is not None:
            stmt = stmt.join(User, Learner.user_id == User.id).where(User.school_id == school_id)
        if learner_ids is not None:  # ADR-031: only learners this viewer may see
            stmt = stmt.where(Learner.id.in_(learner_ids))
        stmt = stmt.order_by(Learner.display_name)
        result = await db.execute(stmt)
        rows = result.all()

        learner_list = []
        for learner, total_attempts, accuracy, last_activity in rows:
            learner_list.append({
                "id": str(learner.id),
                "name": learner.display_name,
                "grade": learner.grade,
                "total_attempts": total_attempts or 0,
                "overall_accuracy": round(float(accuracy), 2) if accuracy is not None else None,
                "last_activity": last_activity.isoformat() if last_activity else None
            })

        return {
            "learners": learner_list,
            "total_learners": len(learner_list)
        }


# ---------------------------------------------------------------------------
# NEW 17 Nov 2026 (ADR-030, class progress dashboard)
# ---------------------------------------------------------------------------

async def _load_topic_rows(db: AsyncSession) -> Dict[UUID, TopicRow]:
    """Every topic with its subject name/grade -- ~115 rows today, one query."""
    rows = (
        await db.execute(
            select(Topic, Subject.name, Subject.grade).join(Subject, Topic.subject_id == Subject.id)
        )
    ).all()
    return {
        t.id: TopicRow(
            id=t.id,
            name=t.name,
            prerequisite_id=t.prerequisite_id,
            subject_name=subject_name,
            grade=grade,
            order_index=t.order_index or 0,
            subject_id=t.subject_id,
        )
        for t, subject_name, grade in rows
    }


async def _load_attempt_rows(db: AsyncSession, learner_ids: List[UUID]) -> List[AttemptRow]:
    """All scored attempts for these learners, flattened -- one query."""
    if not learner_ids:
        return []
    rows = (
        await db.execute(
            select(Attempt.learner_id, Question.topic_id, Attempt.is_correct, Attempt.created_at)
            .join(Question, Attempt.question_id == Question.id)
            .where(Attempt.learner_id.in_(learner_ids))
            .where(Attempt.is_correct.isnot(None))
        )
    ).all()
    return [
        AttemptRow(learner_id=lid, topic_id=tid, is_correct=ok, created_at=at)
        for lid, tid, ok, at in rows
    ]


async def get_class_progress(
    db: AsyncSession,
    scope,
    grade: Optional[int] = None,
    class_id: Optional[UUID] = None,
) -> Dict:
    """
    The TEACH Progress tab payload. Three queries plus the scope lookup,
    regardless of class size; aggregation is pure (class_progress.py).

    UPDATED 17 Nov 2026 (ADR-031): scoped by the viewer's StaffScope, not
    just school_id. Only learners the viewer may see academically are
    listed, and only attempts on subjects the viewer may see FOR THAT
    LEARNER are counted -- a Maths teacher's view of a learner never
    includes that learner's Accounting answers.
    """
    from app.services.school_scope import ALL_SUBJECTS

    visible_ids = scope.academic_learner_ids()
    member_ids = None
    if class_id is not None:
        member_ids = set(
            (await db.execute(select(ClassMember.learner_id).where(ClassMember.class_id == class_id)))
            .scalars()
            .all()
        )

    learners: List[Learner] = []
    if visible_ids:
        stmt = select(Learner).where(Learner.id.in_(visible_ids))
        if grade is not None:
            stmt = stmt.where(Learner.grade == grade)
        if member_ids is not None:
            stmt = stmt.where(Learner.id.in_(member_ids or {None}))
        learners = (await db.execute(stmt.order_by(Learner.display_name))).scalars().all()

    learner_rows = [LearnerRow(id=l.id, name=l.display_name, grade=l.grade) for l in learners]
    topics = await _load_topic_rows(db)
    attempts = [
        a
        for a in await _load_attempt_rows(db, [l.id for l in learners])
        if a.topic_id in topics and scope.can_see_subject(a.learner_id, topics[a.topic_id].subject_id)
    ]
    data = summarize_class_progress(learner_rows, attempts, topics)

    # Grades the viewer can see at all, for the grade chips -- computed
    # without the grade/class filters so switching never empties the chips.
    if visible_ids:
        grade_rows = (
            await db.execute(select(Learner.grade).where(Learner.id.in_(visible_ids)).distinct())
        ).all()
        data["available_grades"] = sorted(g for (g,) in grade_rows)
    else:
        data["available_grades"] = []
    data["grade"] = grade
    data["class_id"] = str(class_id) if class_id else None
    return data
