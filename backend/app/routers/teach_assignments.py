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
from app.core.security import get_current_teacher
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


async def _owned_assignment(db: AsyncSession, assignment_id: str, teacher: User) -> Assignment:
    """
    Shared ownership check -- 404s (not 403) for an assignment that
    exists but belongs to a different teacher, same "don't confirm the
    id was valid for someone else" posture app/routers/admin.py's
    roster scoping uses. Used by both GET .../{id} and the new release
    endpoint below.
    """
    assignment = await db.get(Assignment, assignment_id)
    if assignment is None or assignment.teacher_user_id != teacher.id:
        raise HTTPException(status_code=404, detail="Assignment not found")
    return assignment


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
        target_count=len(payload.learner_ids),
        marks_total=sum(q.marks for q in payload.questions),
    )


@router.get("/assignments", response_model=list[AssignmentSummary])
async def list_assignments(
    teacher: User = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
) -> list[AssignmentSummary]:
    """
    This teacher's own assignments only -- scoped by teacher_user_id,
    not just school_id, so one teacher never sees a colleague's
    assignment roster even within the same school. No Class/group
    concept exists yet (ADR-028), so there's no coarser grouping to
    scope by instead.
    """
    assignments = (
        (
            await db.execute(
                select(Assignment)
                .where(Assignment.teacher_user_id == teacher.id)
                .order_by(Assignment.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    summaries: list[AssignmentSummary] = []
    for assignment in assignments:
        assignment_questions = (
            (
                await db.execute(
                    select(AssignmentQuestion).where(
                        AssignmentQuestion.assignment_id == assignment.id
                    )
                )
            )
            .scalars()
            .all()
        )
        target_count = len(
            (
                await db.execute(
                    select(AssignmentTarget.id).where(
                        AssignmentTarget.assignment_id == assignment.id
                    )
                )
            )
            .scalars()
            .all()
        )
        summaries.append(
            AssignmentSummary(
                id=assignment.id,
                title=assignment.title,
                instructions=assignment.instructions,
                due_at=assignment.due_at,
                created_at=assignment.created_at,
                mode=assignment.mode,
                results_released=assignment.results_released,
                question_count=len(assignment_questions),
                target_count=target_count,
                marks_total=sum(aq.marks for aq in assignment_questions),
            )
        )
    return summaries


@router.get("/assignments/{assignment_id}", response_model=AssignmentDetail)
async def get_assignment(
    assignment_id: str,
    teacher: User = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
) -> AssignmentDetail:
    assignment = await _owned_assignment(db, assignment_id, teacher)

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
        questions=question_items,
        completions=completion_items,
    )


@router.post("/assignments/{assignment_id}/release", response_model=AssignmentSummary)
async def release_results(
    assignment_id: str,
    teacher: User = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
) -> AssignmentSummary:
    """
    NEW (ADR-029): the teacher-controlled switch for a Test-mode
    assignment -- flips results_released so every targeted student's
    withheld is_correct/ai_feedback/marks_earned becomes visible. A no-
    op (not an error) for a "practice" assignment or one already
    released, same "idempotent, harmless to click twice" posture
    release_assignment_results() documents.
    """
    assignment = await _owned_assignment(db, assignment_id, teacher)
    await release_assignment_results(db, assignment=assignment)
    await db.commit()

    assignment_questions = (
        (
            await db.execute(
                select(AssignmentQuestion).where(
                    AssignmentQuestion.assignment_id == assignment.id
                )
            )
        )
        .scalars()
        .all()
    )
    target_count = len(
        (
            await db.execute(
                select(AssignmentTarget.id).where(AssignmentTarget.assignment_id == assignment.id)
            )
        )
        .scalars()
        .all()
    )
    return AssignmentSummary(
        id=assignment.id,
        title=assignment.title,
        instructions=assignment.instructions,
        due_at=assignment.due_at,
        created_at=assignment.created_at,
        mode=assignment.mode,
        results_released=assignment.results_released,
        question_count=len(assignment_questions),
        target_count=target_count,
        marks_total=sum(aq.marks for aq in assignment_questions),
    )
