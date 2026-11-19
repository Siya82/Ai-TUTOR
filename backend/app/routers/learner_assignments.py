"""
Learner-facing Assignments API: listing what's been issued, viewing
one assignment's questions (never including model_answer -- see
app/schemas/assignments.py's LearnerQuestionItem), and submitting an
answer, which is this app's first production path that actually marks
a response and writes a real Attempt row. See docs/ADR-028-assignments.md
and docs/ADR-029-assignment-mode-and-marks.md.

NEW 15 Nov 2026. UPDATED 15 Nov 2026 (ADR-029): a "test"-mode
assignment withholds is_correct/ai_feedback/marks_earned from every
response below until the teacher releases results -- the real mark is
still always computed and written to Attempt (app/services/
assignments.py's submit_assignment_answer()); only what these
endpoints SHOW the student is gated here.
"""

import uuid

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
from app.services.assignments import (
    AssignmentClosed,
    AssignmentError,
    answers_closed_reason,
    get_learner_completions,
    submit_assignment_answer,
)
from app.core.config import settings
from app.services.tutor import TutorClient

router = APIRouter(prefix="/assignments", tags=["assignments"])

# Same module-level singleton pattern app/routers/tutor.py already uses
# for its own TutorClient -- one AsyncAnthropic client reused across
# requests rather than constructed per call.
# UPDATED 19 Nov 2026 (ADR-035): marking may use a cheaper model
# (MARKING_MODEL in .env); empty falls back to ANTHROPIC_MODEL.
_tutor_client = TutorClient(model=settings.marking_model or None)


def _withholds_feedback(assignment: Assignment) -> bool:
    """
    True while this assignment's mark/feedback must stay hidden from
    the student (ADR-029): mode == "test" and the teacher hasn't
    released results yet. "practice" assignments (including every
    assignment created before this feature existed, via the mode
    column's default) never withhold anything.
    """
    return assignment.mode == "test" and not assignment.results_released


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

    # UPDATED 17 Nov 2026 (code review #16): this learner's own completion
    # for every assignment in two queries (same rules as the teacher view),
    # instead of the whole class's recomputed once per assignment.
    mine_by_id = await get_learner_completions(
        db, assignment_ids=[a.id for a in assignments], learner_id=learner.id
    )
    summaries: list[LearnerAssignmentSummary] = []
    for assignment in assignments:
        mine = mine_by_id.get(assignment.id)
        withheld = _withholds_feedback(assignment)
        summaries.append(
            LearnerAssignmentSummary(
                id=assignment.id,
                title=assignment.title,
                instructions=assignment.instructions,
                due_at=assignment.due_at,
                mode=assignment.mode,
                results_released=assignment.results_released,
                answers_closed=answers_closed_reason(assignment),
                status=mine.status if mine else "not_started",
                answered_count=mine.answered_count if mine else 0,
                question_count=mine.question_count if mine else 0,
                marks_total=mine.marks_total if mine else 0,
                marks_earned=None if withheld else (mine.marks_earned if mine else 0),
            )
        )
    return summaries


@router.get("/{assignment_id}", response_model=LearnerAssignmentDetail)
async def get_my_assignment(
    assignment_id: uuid.UUID,
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

    withheld = _withholds_feedback(assignment)

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

    # Ordered so that, if a student ever has more than one Attempt for
    # the same question (the "Re-submit answer" button), the LATEST one
    # wins when building attempts_by_question below -- same dedup fix
    # as get_assignment_completion()'s in app/services/assignments.py.
    attempts = (
        (
            await db.execute(
                select(Attempt)
                .where(
                    Attempt.assignment_id == assignment.id,
                    Attempt.learner_id == learner.id,
                )
                .order_by(Attempt.created_at)
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
        this_withheld = withheld and attempt is not None
        question_items.append(
            LearnerQuestionItem(
                id=question.id,
                text=question.text,
                order_index=aq.order_index,
                marks=aq.marks,
                answered=attempt is not None,
                is_correct=None if this_withheld else (attempt.is_correct if attempt else None),
                ai_feedback=None if this_withheld else (attempt.ai_feedback if attempt else None),
                learner_response=attempt.learner_response if attempt else None,
                feedback_withheld=this_withheld,
                # code review 19 Nov #2: the teacher's correction, when there is one
                teacher_note=None if this_withheld or attempt is None else attempt.teacher_note,
                marked_by_teacher=bool(attempt and attempt.marked_by_user_id and not this_withheld),
            )
        )

    return LearnerAssignmentDetail(
        id=assignment.id,
        title=assignment.title,
        instructions=assignment.instructions,
        due_at=assignment.due_at,
        mode=assignment.mode,
        results_released=assignment.results_released,
        answers_closed=answers_closed_reason(assignment),
        questions=question_items,
    )


@router.post("/{assignment_id}/questions/{question_id}/answer", response_model=AnswerSubmitResult)
async def answer_assignment_question(
    assignment_id: uuid.UUID,
    question_id: uuid.UUID,
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

    FIX (ADR-029 -- this is the actual bug the "an assignment ... should
    not be giving a student hints" report named): this used to always
    return the real is_correct/feedback the instant marking finished,
    even for a "test"-mode assignment, handing the student the correct
    answer's explanation before results were ever meant to be seen.
    The mark is still always computed and stored; it's now withheld
    from the RESPONSE (not the database) exactly as get_my_assignment
    above withholds it on reload.
    """
    assignment = await db.get(Assignment, assignment_id)
    if assignment is None:
        raise HTTPException(status_code=404, detail="Assignment not found")

    try:
        attempt, marks = await submit_assignment_answer(
            db,
            _tutor_client,
            learner=learner,
            assignment_id=assignment_id,
            question_id=question_id,
            learner_response=payload.learner_response,
        )
    except AssignmentClosed as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except AssignmentError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    await db.commit()

    withheld = _withholds_feedback(assignment)
    return AnswerSubmitResult(
        question_id=attempt.question_id,
        marks=marks,
        is_correct=None if withheld else attempt.is_correct,
        feedback=None if withheld else attempt.ai_feedback,
        feedback_withheld=withheld,
    )
