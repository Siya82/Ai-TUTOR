"""
NEW 19 Nov 2026 (ADR-036): the teacher's "Today" panel.

GET  /teach/today           -- who needs help, weak topics, quiet learners,
                               my assignments due soon (last 7 days of answers)
POST /teach/today/practice  -- one click: a short practice set on a weak
                               topic for the learners who struggled with it

Everything is limited to the caller's StaffScope: only learners they may
see academically, and only answers in subjects they may see for that
learner (same rule as the Progress tab, ADR-031).
"""

import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utcnow_naive
from app.core.database import get_db
from app.core.security import get_current_staff_scope, get_current_teacher
from app.models import Assignment, Attempt, Learner, Question, School, Topic, User
from app.services.assignments import AssignmentError, create_assignment, get_assignment_completion
from app.services.dashboard import _load_topic_rows
from app.services.school_scope import StaffScope
from app.services.teacher_today import (
    WINDOW_DAYS,
    Answer,
    TopicInfo,
    make_practice_question_ids,
    summarise_today,
)

router = APIRouter(prefix="/teach/today", tags=["teach"])

DUE_SOON_DAYS = 3


class PracticeRequest(BaseModel):
    topic_id: uuid.UUID
    learner_ids: list[uuid.UUID] = Field(min_length=1, max_length=200)


@router.get("")
async def today(
    scope: StaffScope = Depends(get_current_staff_scope),
    db: AsyncSession = Depends(get_db),
) -> dict:
    now = utcnow_naive()
    ids = scope.academic_learner_ids()
    learners = {}
    if ids:
        learners = {
            l.id: l.display_name
            for l in (await db.execute(select(Learner).where(Learner.id.in_(ids)))).scalars()
        }
    topic_rows = await _load_topic_rows(db)
    topics = {
        tid: TopicInfo(t.id, t.name, t.subject_name, t.grade) for tid, t in topic_rows.items()
    }
    answers: list[Answer] = []
    if learners:
        rows = (
            await db.execute(
                select(
                    Attempt.learner_id,
                    Attempt.question_id,
                    Question.topic_id,
                    Attempt.is_correct,
                    Attempt.created_at,
                )
                .join(Question, Attempt.question_id == Question.id)
                .where(
                    Attempt.learner_id.in_(list(learners)),
                    Attempt.is_correct.isnot(None),
                    Attempt.created_at >= now - timedelta(days=WINDOW_DAYS),
                )
            )
        ).all()
        answers = [
            Answer(lid, qid, tid, bool(ok), at)
            for lid, qid, tid, ok, at in rows
            if tid in topic_rows and scope.can_see_subject(lid, topic_rows[tid].subject_id)
        ]
    data = summarise_today(learners, answers, topics, now)

    # My own assignments due in the next few days, with who's still behind.
    due = (
        await db.execute(
            select(Assignment)
            .where(
                Assignment.teacher_user_id == scope.user_id,
                Assignment.due_at.isnot(None),
                Assignment.due_at >= now - timedelta(days=1),
                Assignment.due_at <= now + timedelta(days=DUE_SOON_DAYS),
            )
            .order_by(Assignment.due_at)
        )
    ).scalars().all()
    due_soon = []
    for a in due:
        completions = await get_assignment_completion(db, assignment_id=a.id)
        due_soon.append(
            {
                "assignment_id": str(a.id),
                "title": a.title,
                "due_at": a.due_at.isoformat(),
                "learners": len(completions),
                "not_finished": sum(1 for c in completions if c.status != "completed"),
            }
        )
    data["due_soon"] = due_soon
    return data


@router.post("/practice")
async def create_practice(
    payload: PracticeRequest,
    teacher: User = Depends(get_current_teacher),
    scope: StaffScope = Depends(get_current_staff_scope),
    db: AsyncSession = Depends(get_db),
) -> dict:
    topic = await db.get(Topic, payload.topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")
    allowed = scope.academic_learner_ids()
    learner_ids = [
        lid for lid in dict.fromkeys(payload.learner_ids)
        if lid in allowed and scope.can_see_subject(lid, topic.subject_id)
    ]
    if not learner_ids:
        raise HTTPException(status_code=400, detail="None of these learners are yours for this subject")

    candidates = (
        await db.execute(
            select(Question.id)
            .where(
                Question.topic_id == topic.id,
                Question.created_by_user_id.is_(None) | (Question.created_by_user_id == teacher.id),
            )
            .order_by(Question.id)
        )
    ).scalars().all()
    if not candidates:
        raise HTTPException(status_code=400, detail="There are no bank questions on this topic yet")
    recently_correct = set(
        (
            await db.execute(
                select(Attempt.question_id).where(
                    Attempt.learner_id.in_(learner_ids),
                    Attempt.is_correct.is_(True),
                    Attempt.created_at >= utcnow_naive() - timedelta(days=30),
                )
            )
        ).scalars().all()
    )
    question_ids = make_practice_question_ids(list(candidates), recently_correct)

    school = await db.get(School, teacher.school_id)
    try:
        assignment = await create_assignment(
            db,
            teacher=teacher,
            school=school,
            title=f"Practice: {topic.name}"[:200],
            instructions="Extra practice on a topic that tripped you up this week. Take your time and read the feedback.",
            due_at=None,
            mode="practice",
            questions=[(qid, 1) for qid in question_ids],
            learner_ids=learner_ids,
            scope=scope,
        )
    except AssignmentError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    await db.commit()
    return {
        "assignment_id": str(assignment.id),
        "title": assignment.title,
        "question_count": len(question_ids),
        "learner_count": len(learner_ids),
    }
