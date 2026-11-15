"""
Learner-facing Assignments API: listing what's been issued, viewing
one assignment's questions (never including model_answer -- see
app/schemas/assignments.py's LearnerQuestionItem), and submitting an
answer, which is this app's first production path that actually marks
a response and writes a real Attempt row. See docs/ADR-028-assignments.md.

NEW 15 Nov 2026.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_learner
from app.models import Assignment, AssignmentQuestion, AssignmentTarget, Attempt, Learner, Question
from app.schemas.assignments import (
    AnswerSubmitRequest,
    AnswerSubmitResult,
    LearnerAssignmentDetail,
    LearnerAssignmentSummary,
    LearnerQuestionItem,
)
from app.services.assignments import AssignmentError, get_assignment_completion, submit_assignment_answer
from app.services.tutor import TutorClient

router = APIRouter(prefix="/assignments", tags=["assignments"])

# Same module-level singleton pattern app/routers/tutor.py already uses
# for its own TutorClient -- one AsyncAnthropic client reused across
# requests rather than constructed per call.
_tutor_client = TutorClient()


@router.get("", response_model=list[LearnerAssignmentSummary])
async def list_my_assignments(
    learner: Learner = Depends(get_current_learner),
    db: AsyncSession = Depends(get_db),
) -> list[LearnerAssignmentSummary]:
    assignment_ids = (
        (
            await db.execute(
                select(AssignmentTarget.assignment_id).where(
                    AssignmentTarget.learner_id == learner.id
                )
            )
        )
        .scalars()
        .all()
    )
    if not assignment_ids:
        return []

    assignments = (
        (
            await db.execute(
                select(Assignment)
                .where(Assignment.id.in_(assignment_ids))
                .order_by(Assignment.created_at.desc())
            )
        )
        .scalars()
        .all()
    )

    summaries: list[LearnerAssignmentSummary] = []
    for assignment in assignments:
        # Reuses the same completion computation the teacher-facing
        # detail view uses (app/services/assignments.py) rather than a
        # second, slightly-different "how much has this learner done"
        # calculation -- one source of truth for completion status.
        completions = await get_assignment_completion(db, assignment_id=assignment.id)
        mine = next((c for c in completions if c.learner_id == learner.id), None)
        summaries.append(
            LearnerAssignmentSummary(
                id=assignment.id,
                title=assignment.title,
                instructions=assignment.instructions,
                due_at=assignment.due_at,
                status=mine.status if mine else "not_started",
                answered_count=mine.answered_count if mine else 0,
                question_count=mine.question_count if mine else 0,
            )
        )
    return summaries


@router.get("/{assignment_id}", response_model=LearnerAssignmentDetail)
async def get_my_assignment(
    assignment_id: str,
    learner: Learner = Depends(get_current_learner),
    db: AsyncSession = Depends(get_db),
) -> LearnerAssignmentDetail:
    targeted = (
        await db.execute(
            select(AssignmentTarget).where(
                AssignmentTarget.assignment_id == assignment_id,
                AssignmentTarget.learner_id == learner.id,
            )
        )
    ).scalar_one_or_none()
    if targeted is None:
        # 404, not 403 -- doesn't confirm to the caller whether the id
        # belongs to someone else's assignment or doesn't exist at all.
        raise HTTPException(status_code=404, detail="Assignment not found")

    assignment = await db.get(Assignment, assignment_id)
    if assignment is None:
        raise HTTPException(status_code=404, detail="Assignment not found")

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
    q_ids = [aq.question_id for aq in assignment_questions]
    questions_by_id = {}
    if q_ids:
        questions = (await db.execute(select(Question).where(Question.id.in_(q_ids)))).scalars().all()
        questions_by_id = {q.id: q for q in questions}

    attempts = (
        (
            await db.execute(
                select(Attempt).where(
                    Attempt.assignment_id == assignment.id,
                    Attempt.learner_id == learner.id,
                )
            )
        )
        .scalars()
        .all()
    )
    attempts_by_question = {a.question_id: a for a in attempts}

    question_items = []
    for aq in assignment_questions:
        question = questions_by_id.get(aq.question_id)
        if question is None:
            continue
        attempt = attempts_by_question.get(aq.question_id)
        question_items.append(
            LearnerQuestionItem(
                id=question.id,
                text=question.text,
                order_index=aq.order_index,
                answered=attempt is not None,
                is_correct=attempt.is_correct if attempt else None,
                ai_feedback=attempt.ai_feedback if attempt else None,
                learner_response=attempt.learner_response if attempt else None,
            )
        )

    return LearnerAssignmentDetail(
        id=assignment.id,
        title=assignment.title,
        instructions=assignment.instructions,
        due_at=assignment.due_at,
        questions=question_items,
    )


@router.post("/{assignment_id}/questions/{question_id}/answer", response_model=AnswerSubmitResult)
async def answer_assignment_question(
    assignment_id: str,
    question_id: str,
    payload: AnswerSubmitRequest,
    learner: Learner = Depends(get_current_learner),
    db: AsyncSession = Depends(get_db),
) -> AnswerSubmitResult:
    """
    The actual submit -> mark -> write-Attempt flow. Both of
    submit_assignment_answer()'s AssignmentError cases (not targeted;
    question not part of this assignment) become a 403 here -- either
    way this learner has no business answering this question under
    this assignment_id, which is an authorization fact, not a bad
    request-body fact (unlike AssignmentCreateRequest validation on
    the teacher side, which 400s).
    """
    try:
        attempt = await submit_assignment_answer(
            db,
            _tutor_client,
            learner=learner,
            assignment_id=assignment_id,
            question_id=question_id,
            learner_response=payload.learner_response,
        )
    except AssignmentError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    await db.commit()
    return AnswerSubmitResult(
        question_id=attempt.question_id,
        is_correct=attempt.is_correct,
        feedback=attempt.ai_feedback,
    )
