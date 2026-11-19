"""
Teacher-facing Assignments API: authoring custom questions, browsing
the reusable question bank, creating assignments (school/roster-
scoped), viewing an assignment's roster-wide completion, and releasing
a Test-mode assignment's withheld results. See
docs/ADR-028-assignments.md and docs/ADR-029-assignment-mode-and-marks.md.

NEW 15 Nov 2026. UPDATED 15 Nov 2026 (ADR-029): per-question marks,
practice/test mode, results release, GET /teach/questions bank browse.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_staff_scope, get_current_teacher
from app.services.school_scope import DEPARTMENTAL_HEAD, StaffScope
from app.models import (
    Assignment,
    AssignmentQuestion,
    AssignmentTarget,
    Learner,
    Question,
    School,
    Topic,
    User,
)
from app.schemas.assignments import (
    AssignmentCreateRequest,
    AssignmentDetail,
    AssignmentQuestionItem,
    AssignmentSummary,
    CustomQuestionCreateRequest,
    CustomQuestionResult,
    LearnerCompletionItem,
)
from app.services.assignments import (
    AssignmentError,
    answers_closed_reason,
    create_assignment,
    create_custom_question,
    get_assignment_completion,
    list_bank_questions_for_topic,
    release_assignment_results,
)

router = APIRouter(prefix="/teach", tags=["assignments"])


async def _teacher_school(db: AsyncSession, teacher: User) -> School:
    school = await db.get(School, teacher.school_id)
    if school is None:
        # Should be unreachable -- School.id is a required FK on User --
        # but fail loudly if it's ever wrong rather than silently 404ing.
        # Same guard app/routers/admin.py's _teacher_school uses.
        raise HTTPException(status_code=500, detail="Teacher account has no linked school")
    return school


async def _visible_assignment(
    db: AsyncSession, assignment_id: uuid.UUID, scope: StaffScope
) -> tuple[Assignment, "_Facts"]:
    """
    UPDATED 17 Nov 2026 (code review #12). Used to be owner-only. Now an
    assignment is visible to the teacher who set it, to the principal and
    deputy (whole school), and to a departmental head whose subject it
    covers for any of its learners. Anyone else gets a 404 (not 403), so
    an id that belongs to someone else isn't confirmed.
    """
    assignment = await db.get(Assignment, assignment_id)
    if assignment is None or assignment.school_id != scope.school_id:
        raise HTTPException(status_code=404, detail="Assignment not found")
    facts = (await _load_facts(db, [assignment.id]))[assignment.id]
    if not _can_view(scope, assignment, facts):
        raise HTTPException(status_code=404, detail="Assignment not found")
    return assignment, facts


class _Facts:
    """Per-assignment numbers gathered in a few batched queries (code review #16)."""

    def __init__(self) -> None:
        self.subject_ids: set[uuid.UUID] = set()
        self.learner_ids: list[uuid.UUID] = []
        self.question_count = 0
        self.marks_total = 0


async def _load_facts(db: AsyncSession, assignment_ids: list[uuid.UUID]) -> dict[uuid.UUID, _Facts]:
    facts = {aid: _Facts() for aid in assignment_ids}
    if not assignment_ids:
        return facts
    q_rows = (
        await db.execute(
            select(AssignmentQuestion.assignment_id, AssignmentQuestion.marks, Topic.subject_id)
            .join(Question, AssignmentQuestion.question_id == Question.id)
            .join(Topic, Question.topic_id == Topic.id)
            .where(AssignmentQuestion.assignment_id.in_(assignment_ids))
        )
    ).all()
    for aid, marks, subject_id in q_rows:
        f = facts[aid]
        f.subject_ids.add(subject_id)
        f.question_count += 1
        f.marks_total += marks
    t_rows = (
        await db.execute(
            select(AssignmentTarget.assignment_id, AssignmentTarget.learner_id).where(
                AssignmentTarget.assignment_id.in_(assignment_ids)
            )
        )
    ).all()
    for aid, learner_id in t_rows:
        facts[aid].learner_ids.append(learner_id)
    return facts


def _can_view(scope: StaffScope, assignment: Assignment, facts: _Facts) -> bool:
    if assignment.teacher_user_id == scope.user_id or scope.whole_school_academic:
        return True
    if DEPARTMENTAL_HEAD in scope.role_names:
        return any(
            scope.can_see_subject(lid, sid) for lid in facts.learner_ids for sid in facts.subject_ids
        )
    return False


def _can_release(scope: StaffScope, assignment: Assignment) -> bool:
    return assignment.teacher_user_id == scope.user_id or scope.can_manage_school


async def _teacher_names(db: AsyncSession, user_ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
    if not user_ids:
        return {}
    rows = (
        await db.execute(
            select(User.id, User.display_name, User.student_number).where(User.id.in_(user_ids))
        )
    ).all()
    return {uid: (name or number) for uid, name, number in rows}


def _summary(
    assignment: Assignment, facts: _Facts, scope: StaffScope, names: dict[uuid.UUID, str]
) -> AssignmentSummary:
    return AssignmentSummary(
        id=assignment.id,
        title=assignment.title,
        instructions=assignment.instructions,
        due_at=assignment.due_at,
        created_at=assignment.created_at,
        mode=assignment.mode,
        results_released=assignment.results_released,
        question_count=facts.question_count,
        target_count=len(facts.learner_ids),
        marks_total=facts.marks_total,
        is_mine=assignment.teacher_user_id == scope.user_id,
        teacher_name=names.get(assignment.teacher_user_id),
        can_release=_can_release(scope, assignment),
    )


@router.post("/questions", response_model=CustomQuestionResult)
async def create_question(
    payload: CustomQuestionCreateRequest,
    teacher: User = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
) -> CustomQuestionResult:
    """
    A teacher-authored question, reusable across any number of future
    assignments (not assignment-exclusive -- ADR-028's Scope section).
    """
    topic = await db.get(Topic, payload.topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Unknown topic_id")

    question = create_custom_question(
        teacher=teacher,
        topic_id=payload.topic_id,
        text=payload.text,
        model_answer=payload.model_answer,
    )
    db.add(question)
    await db.commit()
    return CustomQuestionResult(
        id=question.id,
        topic_id=question.topic_id,
        text=question.text,
        model_answer=question.model_answer,
        created_at=question.created_at,
        created_by_user_id=question.created_by_user_id,
    )


@router.get("/questions", response_model=list[CustomQuestionResult])
async def list_questions_for_topic(
    topic_id: uuid.UUID,
    teacher: User = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
) -> list[CustomQuestionResult]:
    """
    NEW (ADR-029): the question-bank browse list a teacher sees in
    CreateAssignmentForm once a topic is picked -- every seeded CAPS
    question for the topic, plus this teacher's own previously-
    authored custom ones, so a question can be reused across more than
    one assignment instead of only ever being written fresh.
    """
    topic = await db.get(Topic, topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Unknown topic_id")

    questions = await list_bank_questions_for_topic(db, teacher=teacher, topic_id=topic_id)
    return [
        CustomQuestionResult(
            id=q.id,
            topic_id=q.topic_id,
            text=q.text,
            model_answer=q.model_answer,
            created_at=q.created_at,
            created_by_user_id=q.created_by_user_id,
        )
        for q in questions
    ]


@router.post("/assignments", response_model=AssignmentSummary)
async def create_new_assignment(
    payload: AssignmentCreateRequest,
    teacher: User = Depends(get_current_teacher),
    scope: StaffScope = Depends(get_current_staff_scope),
    db: AsyncSession = Depends(get_db),
) -> AssignmentSummary:
    school = await _teacher_school(db, teacher)
    try:
        assignment = await create_assignment(
            db,
            teacher=teacher,
            school=school,
            title=payload.title,
            instructions=payload.instructions,
            due_at=payload.due_at,
            mode=payload.mode,
            questions=[(q.question_id, q.marks) for q in payload.questions],
            learner_ids=payload.learner_ids,
            class_ids=payload.class_ids,
            scope=scope,
        )
    except AssignmentError as exc:
        # Bad input (unknown question id, a student outside this
        # teacher's own school, an empty list) -- the caller's mistake
        # to fix, not a server error. Same split provision_student's
        # RuntimeError gets in app/routers/admin.py.
        raise HTTPException(status_code=400, detail=str(exc))
    await db.commit()
    return AssignmentSummary(
        id=assignment.id,
        title=assignment.title,
        instructions=assignment.instructions,
        due_at=assignment.due_at,
        created_at=assignment.created_at,
        mode=assignment.mode,
        results_released=assignment.results_released,
        question_count=len(payload.questions),
        target_count=len(
            (
                await db.execute(
                    select(AssignmentTarget.id).where(AssignmentTarget.assignment_id == assignment.id)
                )
            ).scalars().all()
        ),
        marks_total=sum(q.marks for q in payload.questions),
    )


@router.get("/assignments", response_model=list[AssignmentSummary])
async def list_assignments(
    scope: StaffScope = Depends(get_current_staff_scope),
    db: AsyncSession = Depends(get_db),
) -> list[AssignmentSummary]:
    """
    UPDATED 17 Nov 2026 (code review #12, #16): the caller's own
    assignments plus the ones they oversee (see _visible_assignment),
    newest first, gathered in a fixed number of queries.
    """
    assignments = (
        (
            await db.execute(
                select(Assignment)
                .where(Assignment.school_id == scope.school_id)
                .order_by(Assignment.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    facts = await _load_facts(db, [a.id for a in assignments])
    visible = [a for a in assignments if _can_view(scope, a, facts[a.id])]
    names = await _teacher_names(db, {a.teacher_user_id for a in visible})
    return [_summary(a, facts[a.id], scope, names) for a in visible]


@router.get("/assignments/{assignment_id}", response_model=AssignmentDetail)
async def get_assignment(
    assignment_id: uuid.UUID,
    scope: StaffScope = Depends(get_current_staff_scope),
    db: AsyncSession = Depends(get_db),
) -> AssignmentDetail:
    assignment, _facts = await _visible_assignment(db, assignment_id, scope)

    assignment_questions = (
        (
            await db.execute(
                select(AssignmentQuestion)
                .where(AssignmentQuestion.assignment_id == assignment.id)
                .order_by(AssignmentQuestion.order_index)
            )
        )
        .scalars()
        .all()
    )
    questions_by_id = {}
    if assignment_questions:
        q_ids = [aq.question_id for aq in assignment_questions]
        questions = (
            (await db.execute(select(Question).where(Question.id.in_(q_ids)))).scalars().all()
        )
        questions_by_id = {q.id: q for q in questions}

    question_items = [
        AssignmentQuestionItem(
            id=aq.question_id,
            text=questions_by_id[aq.question_id].text,
            model_answer=questions_by_id[aq.question_id].model_answer,
            order_index=aq.order_index,
            marks=aq.marks,
        )
        for aq in assignment_questions
        if aq.question_id in questions_by_id
    ]

    completions = await get_assignment_completion(db, assignment_id=assignment.id)
    learner_ids = [c.learner_id for c in completions]
    learners_by_id = {}
    if learner_ids:
        learners = (
            (await db.execute(select(Learner).where(Learner.id.in_(learner_ids)))).scalars().all()
        )
        learners_by_id = {l.id: l for l in learners}

    completion_items = [
        LearnerCompletionItem(
            learner_id=c.learner_id,
            display_name=learners_by_id[c.learner_id].display_name
            if c.learner_id in learners_by_id
            else "(unknown student)",
            status=c.status,
            answered_count=c.answered_count,
            question_count=c.question_count,
            correct_count=c.correct_count,
            marks_earned=c.marks_earned,
            marks_total=c.marks_total,
        )
        for c in completions
    ]

    return AssignmentDetail(
        id=assignment.id,
        title=assignment.title,
        instructions=assignment.instructions,
        due_at=assignment.due_at,
        created_at=assignment.created_at,
        mode=assignment.mode,
        results_released=assignment.results_released,
        answers_closed=answers_closed_reason(assignment),
        closed=assignment.closed_at is not None,
        can_change=_can_release(scope, assignment),
        questions=question_items,
        completions=completion_items,
    )


@router.post("/assignments/{assignment_id}/release", response_model=AssignmentSummary)
async def release_results(
    assignment_id: uuid.UUID,
    scope: StaffScope = Depends(get_current_staff_scope),
    db: AsyncSession = Depends(get_db),
) -> AssignmentSummary:
    """
    NEW (ADR-029): the switch that shows a Test's withheld marks and
    feedback to its students. Idempotent. UPDATED 17 Nov 2026 (code
    review #12): the teacher who set it, or school management, may
    release; someone who can only view it gets a 403.
    """
    assignment, facts = await _visible_assignment(db, assignment_id, scope)
    if not _can_release(scope, assignment):
        raise HTTPException(status_code=403, detail="Only the teacher who set this can release its results")
    await release_assignment_results(db, assignment=assignment)
    await db.commit()
    names = await _teacher_names(db, {assignment.teacher_user_id})
    return _summary(assignment, facts, scope, names)


# ---------------------------------------------------------------------------
# NEW 19 Nov 2026 (code review 19 Nov #2): see what each learner wrote, and
# correct the AI's mark. (#7): edit, extend, close, duplicate, delete.
# Changing anything is for the teacher who set it, or school management --
# the same people who may release results.
# ---------------------------------------------------------------------------

from datetime import datetime, timezone  # noqa: E402

from pydantic import BaseModel, Field  # noqa: E402
from sqlalchemy import delete, func  # noqa: E402

from app.core.clock import utcnow_naive  # noqa: E402
from app.models import Attempt  # noqa: E402
from app.services.audit import record as audit  # noqa: E402


def _require_owner(scope: StaffScope, assignment: Assignment) -> None:
    if not _can_release(scope, assignment):
        raise HTTPException(status_code=403, detail="Only the teacher who set this, or school management, can change it")


@router.get("/assignments/{assignment_id}/learners/{learner_id}/answers")
async def learner_answers(
    assignment_id: uuid.UUID,
    learner_id: uuid.UUID,
    scope: StaffScope = Depends(get_current_staff_scope),
    db: AsyncSession = Depends(get_db),
) -> dict:
    assignment, facts = await _visible_assignment(db, assignment_id, scope)
    if learner_id not in facts.learner_ids:
        raise HTTPException(status_code=404, detail="That learner wasn't given this assignment")
    learner = await db.get(Learner, learner_id)
    aqs = (
        await db.execute(
            select(AssignmentQuestion, Question)
            .join(Question, AssignmentQuestion.question_id == Question.id)
            .where(AssignmentQuestion.assignment_id == assignment.id)
            .order_by(AssignmentQuestion.order_index)
        )
    ).all()
    attempts = (
        await db.execute(
            select(Attempt)
            .where(Attempt.assignment_id == assignment.id, Attempt.learner_id == learner_id)
            .order_by(Attempt.created_at)
        )
    ).scalars().all()
    by_q: dict[uuid.UUID, list[Attempt]] = {}
    for at in attempts:
        by_q.setdefault(at.question_id, []).append(at)
    items = []
    for aq, q in aqs:
        tries = by_q.get(q.id, [])
        latest = tries[-1] if tries else None
        items.append(
            {
                "question_id": str(q.id),
                "text": q.text,
                "model_answer": q.model_answer,
                "marks": aq.marks,
                "tries": len(tries),
                "attempt_id": str(latest.id) if latest else None,
                "learner_response": latest.learner_response if latest else None,
                "is_correct": latest.is_correct if latest else None,
                "ai_feedback": latest.ai_feedback if latest else None,
                "teacher_note": latest.teacher_note if latest else None,
                "marked_by_teacher": bool(latest and latest.marked_by_user_id),
                "answered_at": latest.created_at.isoformat() if latest else None,
            }
        )
    return {
        "learner_id": str(learner_id),
        "display_name": learner.display_name if learner else "",
        "can_mark": _can_release(scope, assignment),
        "questions": items,
    }


class MarkOverride(BaseModel):
    is_correct: bool
    note: str | None = Field(default=None, max_length=1000)


@router.post("/assignments/{assignment_id}/attempts/{attempt_id}/mark")
async def override_mark(
    assignment_id: uuid.UUID,
    attempt_id: uuid.UUID,
    payload: MarkOverride,
    scope: StaffScope = Depends(get_current_staff_scope),
    db: AsyncSession = Depends(get_db),
) -> dict:
    assignment, _ = await _visible_assignment(db, assignment_id, scope)
    _require_owner(scope, assignment)
    attempt = await db.get(Attempt, attempt_id)
    if attempt is None or attempt.assignment_id != assignment.id:
        raise HTTPException(status_code=404, detail="Answer not found")
    before = attempt.is_correct
    attempt.is_correct = payload.is_correct
    attempt.teacher_note = (payload.note or "").strip() or None
    attempt.marked_by_user_id = scope.user_id
    attempt.marked_at = utcnow_naive()
    await audit(db, scope.user_id, scope.school_id, "mark.override", "attempt", attempt.id,
                {"assignment_id": str(assignment.id), "from": before, "to": payload.is_correct})
    await db.commit()
    return {"attempt_id": str(attempt.id), "is_correct": attempt.is_correct, "teacher_note": attempt.teacher_note}


class AssignmentEdit(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    instructions: str | None = Field(default=None, max_length=4000)
    due_at: datetime | None = None


@router.patch("/assignments/{assignment_id}")
async def edit_assignment(
    assignment_id: uuid.UUID,
    payload: AssignmentEdit,
    scope: StaffScope = Depends(get_current_staff_scope),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Title, instructions, due date (extend it, or set one). Questions and
    learners stay fixed once issued -- duplicate to make a changed copy."""
    assignment, _ = await _visible_assignment(db, assignment_id, scope)
    _require_owner(scope, assignment)
    assignment.title = payload.title.strip()
    assignment.instructions = (payload.instructions or "").strip() or None
    due = payload.due_at
    if due is not None and due.tzinfo is not None:  # stored as naive UTC, like every timestamp here
        due = due.astimezone(timezone.utc).replace(tzinfo=None)
    assignment.due_at = due
    await db.commit()
    return {"id": str(assignment.id), "title": assignment.title, "due_at": assignment.due_at}


@router.post("/assignments/{assignment_id}/close")
async def close_assignment(
    assignment_id: uuid.UUID,
    reopen: bool = False,
    scope: StaffScope = Depends(get_current_staff_scope),
    db: AsyncSession = Depends(get_db),
) -> dict:
    assignment, _ = await _visible_assignment(db, assignment_id, scope)
    _require_owner(scope, assignment)
    assignment.closed_at = None if reopen else utcnow_naive()
    await db.commit()
    return {"id": str(assignment.id), "closed": assignment.closed_at is not None}


@router.post("/assignments/{assignment_id}/duplicate")
async def duplicate_assignment(
    assignment_id: uuid.UUID,
    scope: StaffScope = Depends(get_current_staff_scope),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """A fresh copy (same questions, marks and learners) the caller owns."""
    assignment, facts = await _visible_assignment(db, assignment_id, scope)
    copy = Assignment(
        school_id=assignment.school_id,
        teacher_user_id=scope.user_id,
        title=f"{assignment.title} (copy)"[:200],
        instructions=assignment.instructions,
        mode=assignment.mode,
    )
    db.add(copy)
    await db.flush()
    for aq in (
        await db.execute(select(AssignmentQuestion).where(AssignmentQuestion.assignment_id == assignment.id))
    ).scalars():
        db.add(AssignmentQuestion(assignment_id=copy.id, question_id=aq.question_id, order_index=aq.order_index,
                                  marks=aq.marks))
    for lid in set(facts.learner_ids):
        db.add(AssignmentTarget(assignment_id=copy.id, learner_id=lid))
    await db.commit()
    return {"id": str(copy.id), "title": copy.title}


@router.delete("/assignments/{assignment_id}", status_code=204)
async def delete_assignment(
    assignment_id: uuid.UUID,
    scope: StaffScope = Depends(get_current_staff_scope),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Only before anyone has answered -- afterwards, close it instead, so
    learners' work and marks are never thrown away."""
    assignment, _ = await _visible_assignment(db, assignment_id, scope)
    _require_owner(scope, assignment)
    answered = (
        await db.execute(select(func.count()).select_from(Attempt).where(Attempt.assignment_id == assignment.id))
    ).scalar_one()
    if answered:
        raise HTTPException(status_code=409, detail="Learners have already answered this. Close it instead of deleting.")
    await db.execute(delete(AssignmentTarget).where(AssignmentTarget.assignment_id == assignment.id))
    await db.execute(delete(AssignmentQuestion).where(AssignmentQuestion.assignment_id == assignment.id))
    await db.execute(delete(Assignment).where(Assignment.id == assignment.id))
    await audit(db, scope.user_id, scope.school_id, "assignment.delete", "assignment", assignment.id,
                {"title": assignment.title})
    await db.commit()

