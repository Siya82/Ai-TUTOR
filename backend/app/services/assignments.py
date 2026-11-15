"""
Assignments: teacher-side creation (custom questions, assignments with
school/roster scoping) and the learner-facing answer-submission flow
that writes this app's first-ever real Attempt rows. See
docs/ADR-028-assignments.md for the full design and the finding that
no Attempt row had ever been written in production before this.

NEW 15 Nov 2026.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Assignment,
    AssignmentQuestion,
    AssignmentTarget,
    Attempt,
    Learner,
    Question,
    School,
    User,
)
from app.services.answer_marking import MarkingResult, mark_answer
from app.services.tutor import TutorClient


class AssignmentError(ValueError):
    """
    Raised for a caller mistake a router should turn into a 400/403/404
    -- never a bare ValueError, so routers can catch this specifically
    (same reasoning as provision_student's RuntimeError in auth.py)
    without also swallowing a real bug as if it were bad input.
    """


def create_custom_question(
    *, teacher: User, topic_id: uuid.UUID, text: str, model_answer: str
) -> Question:
    """
    Builds (does not add/commit) a teacher-authored Question. Not an
    `async def` -- no DB access is needed to construct the row; the
    caller (the router) does db.add() + db.commit(), the same
    pure-construction-vs-DB split provision_student() uses in auth.py.

    Deliberately does not scope-check topic_id against anything -- the
    Topic table is shared CAPS curriculum data with no school_id at
    all, so there's no cross-school leak to guard against here, unlike
    the learner_id targeting in create_assignment() below.
    """
    return Question(
        topic_id=topic_id,
        text=text,
        model_answer=model_answer,
        is_diagnostic=False,
        is_ai_generated=False,
        created_by_user_id=teacher.id,
    )


async def create_assignment(
    db: AsyncSession,
    *,
    teacher: User,
    school: School,
    title: str,
    instructions: str | None,
    due_at: datetime | None,
    question_ids: list[uuid.UUID],
    learner_ids: list[uuid.UUID],
) -> Assignment:
    """
    Creates (adds, does not commit) an Assignment plus its
    AssignmentQuestion and AssignmentTarget rows.

    "The picker isn't the boundary" (ADR-024/ADR-026, reapplied for
    ADR-028): learner_ids is independently re-validated against this
    teacher's own school via the User join below -- a teacher's own UI
    should never offer another school's student, but this is the
    actual enforcement, not the UI. question_ids are checked only for
    existence, not school-scoped the same way: Question has no
    school_id (the diagnostic/AI-generated bank is shared across every
    school, and a teacher's own custom questions are reusable rather
    than assignment- or school-exclusive, per ADR-028's Scope section)
    -- a bogus/foreign id 400s instead of silently creating a
    half-empty assignment.
    """
    if not question_ids:
        raise AssignmentError("An assignment needs at least one question")
    if not learner_ids:
        raise AssignmentError("An assignment needs at least one target student")

    # FIX 15 Nov 2026 (live-test finding): every timestamp column in this
    # schema (created_at everywhere, via datetime.utcnow()) is naive --
    # TIMESTAMP WITHOUT TIME ZONE. due_at is this app's first-ever
    # CLIENT-SUPPLIED datetime, and the frontend sends an ISO string
    # with a trailing "Z" (toISOString()), which pydantic parses into a
    # timezone-AWARE datetime -- asyncpg then refuses to bind that into
    # a naive column ("can't subtract offset-naive and offset-aware
    # datetimes"), 500ing the very first real Create assignment attempt.
    # Normalized here to naive UTC rather than widening the column to
    # TIMESTAMP WITH TIME ZONE, to stay consistent with every other
    # timestamp this app already stores.
    if due_at is not None and due_at.tzinfo is not None:
        due_at = due_at.astimezone(timezone.utc).replace(tzinfo=None)

    existing_q_ids = set(
        (await db.execute(select(Question.id).where(Question.id.in_(question_ids))))
        .scalars()
        .all()
    )
    missing_q = set(question_ids) - existing_q_ids
    if missing_q:
        raise AssignmentError(
            f"Unknown question id(s): {', '.join(str(i) for i in missing_q)}"
        )

    roster_stmt = (
        select(Learner.id)
        .join(User, Learner.user_id == User.id)
        .where(
            User.school_id == school.id,
            User.role == "student",
            Learner.id.in_(learner_ids),
        )
    )
    valid_learner_ids = set((await db.execute(roster_stmt)).scalars().all())
    missing_learners = set(learner_ids) - valid_learner_ids
    if missing_learners:
        raise AssignmentError(
            "Student id(s) not in this school's roster: "
            + ", ".join(str(i) for i in missing_learners)
        )

    assignment = Assignment(
        school_id=school.id,
        teacher_user_id=teacher.id,
        title=title,
        instructions=instructions,
        due_at=due_at,
    )
    db.add(assignment)
    await db.flush()  # need assignment.id for the child rows below

    for order_index, question_id in enumerate(question_ids):
        db.add(
            AssignmentQuestion(
                assignment_id=assignment.id,
                question_id=question_id,
                order_index=order_index,
            )
        )
    for learner_id in learner_ids:
        db.add(AssignmentTarget(assignment_id=assignment.id, learner_id=learner_id))

    return assignment


async def submit_assignment_answer(
    db: AsyncSession,
    tutor_client: TutorClient,
    *,
    learner: Learner,
    assignment_id: uuid.UUID,
    question_id: uuid.UUID,
    learner_response: str,
) -> Attempt:
    """
    The real "submit -> mark -> write Attempt" flow ADR-028 names as
    this feature's actual architectural payload (see that ADR's
    Context section). Re-validates, server-side, that this learner was
    actually targeted for this assignment AND that this question
    actually belongs to it -- a learner's own client only ever shows
    what it was told to show, but that's not the boundary (same
    principle as create_assignment()'s learner_ids check above,
    applied here on the submit side).
    """
    targeted = (
        await db.execute(
            select(AssignmentTarget).where(
                AssignmentTarget.assignment_id == assignment_id,
                AssignmentTarget.learner_id == learner.id,
            )
        )
    ).scalar_one_or_none()
    if targeted is None:
        raise AssignmentError("This assignment was not issued to this student")

    in_assignment = (
        await db.execute(
            select(AssignmentQuestion).where(
                AssignmentQuestion.assignment_id == assignment_id,
                AssignmentQuestion.question_id == question_id,
            )
        )
    ).scalar_one_or_none()
    if in_assignment is None:
        raise AssignmentError("This question is not part of this assignment")

    question = await db.get(Question, question_id)
    if question is None:
        # Should be unreachable -- AssignmentQuestion.question_id is a
        # required FK -- but fail loudly rather than use None.text below.
        raise AssignmentError("Question not found")

    result: MarkingResult = await mark_answer(
        tutor_client,
        question_text=question.text,
        model_answer=question.model_answer,
        learner_response=learner_response,
    )

    attempt = Attempt(
        learner_id=learner.id,
        question_id=question_id,
        learner_response=learner_response,
        is_correct=result.is_correct,
        ai_feedback=result.feedback,
        assignment_id=assignment_id,
    )
    db.add(attempt)
    return attempt


@dataclass
class LearnerCompletion:
    learner_id: uuid.UUID
    status: str  # "not_started" | "in_progress" | "completed"
    answered_count: int
    question_count: int
    # Out of answered_count. An attempt with is_correct=None (marking
    # failed -- see answer_marking.py) counts toward answered_count but
    # not correct_count -- it's neither right nor wrong, it's unmarked.
    correct_count: int


async def get_assignment_completion(
    db: AsyncSession, *, assignment_id: uuid.UUID
) -> list[LearnerCompletion]:
    """
    Per-target completion, computed on the fly from Attempt rows --
    matching this project's existing "never store what you can derive"
    pattern (personalization.py's pace tier, ADR-002). Deliberately
    scoped by assignment_id on the Attempt side, not bare
    (learner_id, question_id): a learner who answers the SAME question
    outside this assignment (e.g. ordinary adaptive practice) must not
    count toward THIS assignment's completion, which is exactly why
    Attempt.assignment_id exists rather than inferring from a reused
    question_id match.
    """
    targets = (
        (
            await db.execute(
                select(AssignmentTarget).where(
                    AssignmentTarget.assignment_id == assignment_id
                )
            )
        )
        .scalars()
        .all()
    )
    assignment_questions = (
        (
            await db.execute(
                select(AssignmentQuestion).where(
                    AssignmentQuestion.assignment_id == assignment_id
                )
            )
        )
        .scalars()
        .all()
    )
    total_questions = len(assignment_questions)

    results: list[LearnerCompletion] = []
    for target in targets:
        attempts = (
            (
                await db.execute(
                    select(Attempt).where(
                        Attempt.assignment_id == assignment_id,
                        Attempt.learner_id == target.learner_id,
                    )
                )
            )
            .scalars()
            .all()
        )
        answered_question_ids = {a.question_id for a in attempts}
        correct_count = sum(1 for a in attempts if a.is_correct is True)
        if not answered_question_ids:
            status = "not_started"
        elif total_questions > 0 and len(answered_question_ids) >= total_questions:
            status = "completed"
        else:
            status = "in_progress"
        results.append(
            LearnerCompletion(
                learner_id=target.learner_id,
                status=status,
                answered_count=len(answered_question_ids),
                question_count=total_questions,
                correct_count=correct_count,
            )
        )
    return results
