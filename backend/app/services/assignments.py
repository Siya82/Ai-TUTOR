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
    ClassMember,
    Learner,
    Question,
    School,
    SchoolClass,
    Topic,
    User,
)
from app.services.answer_marking import MarkingResult, mark_answer
from app.services.tutor import TutorClient


class AssignmentClosed(Exception):
    """
    NEW 17 Nov 2026 (code review #2). The assignment no longer accepts
    answers: a test whose results are released, or a test past its due
    date. Routers turn this into a 409 with the message as-is.
    """


def answers_closed_reason(assignment: "Assignment", now: datetime | None = None) -> str | None:
    """
    Why this assignment won't take answers right now, or None if it will.
    Practice work always stays open (late practice is still practice);
    a test closes once results are released (otherwise a student could
    read the feedback and re-submit for a better mark) or once its due
    date has passed. due_at is stored as naive UTC, like every timestamp here.
    """
    if assignment.mode != "test":
        return None
    if assignment.results_released:
        return "Results for this test have been released, so answers can no longer be changed."
    now = now or datetime.now(timezone.utc).replace(tzinfo=None)
    if assignment.due_at is not None and now > assignment.due_at:
        return "This test is past its due date, so it no longer accepts answers."
    return None


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
    mode: str = "practice",
    questions: list[tuple[uuid.UUID, int]],
    learner_ids: list[uuid.UUID],
    class_ids: list[uuid.UUID] | None = None,
    scope=None,
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

    `questions` is a list of (question_id, marks) pairs (ADR-029) --
    marks is the point value this question is worth IN THIS
    assignment, already validated to be >= 1 by
    AssignmentQuestionInput before this is called.
    """
    if not questions:
        raise AssignmentError("An assignment needs at least one question")

    # NEW 17 Nov 2026 (ADR-031): whole classes can be targeted; expanded
    # here on the server to their current members, de-duplicated against
    # any individually-picked learners. Each class must be in this school.
    learner_ids = list(dict.fromkeys(learner_ids))
    if class_ids:
        classes = (
            await db.execute(
                select(SchoolClass).where(
                    SchoolClass.id.in_(class_ids), SchoolClass.school_id == school.id
                )
            )
        ).scalars().all()
        if len(classes) != len(set(class_ids)):
            raise AssignmentError("One or more classes are not in this school")
        members = (
            await db.execute(
                select(ClassMember.learner_id).where(ClassMember.class_id.in_(class_ids))
            )
        ).scalars().all()
        for lid in members:
            if lid not in learner_ids:
                learner_ids.append(lid)
    if not learner_ids:
        raise AssignmentError("An assignment needs at least one target student")
    if mode not in ("practice", "test"):
        # Unreachable via the API (AssignmentCreateRequest.mode is a
        # Literal), but fail loudly rather than silently store a typo'd
        # mode no router will ever gate on correctly.
        raise AssignmentError(f"Unknown assignment mode: {mode}")

    question_ids = [qid for qid, _marks in questions]

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

    # UPDATED 17 Nov 2026 (code review #8): only the shared CAPS bank or this
    # teacher's own questions. Another teacher's custom question (and its
    # model answer) is private to them, same rule as the bank browse list.
    existing_q_ids = set(
        (
            await db.execute(
                select(Question.id).where(
                    Question.id.in_(question_ids),
                    Question.created_by_user_id.is_(None)
                    | (Question.created_by_user_id == teacher.id),
                )
            )
        )
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

    # NEW 17 Nov 2026 (ADR-031): school membership isn't enough any more.
    # Every target learner must be one the caller may assign work to in
    # EVERY subject the questions come from -- a Maths teacher can't send
    # a Physical Sciences question to a learner they only teach Maths, or
    # any work to a learner outside their classes.
    if scope is not None:
        subject_by_question = dict(
            (
                await db.execute(
                    select(Question.id, Topic.subject_id)
                    .join(Topic, Question.topic_id == Topic.id)
                    .where(Question.id.in_(question_ids))
                )
            ).all()
        )
        needed = set(subject_by_question.values())
        not_allowed = [
            lid
            for lid in learner_ids
            if not all(scope.can_see_subject(lid, sid) for sid in needed)
        ]
        if not_allowed:
            raise AssignmentError(
                f"{len(not_allowed)} selected student(s) are not in your classes for this "
                "subject. You can only assign work to learners you teach (or oversee) in it."
            )

    assignment = Assignment(
        school_id=school.id,
        teacher_user_id=teacher.id,
        title=title,
        instructions=instructions,
        due_at=due_at,
        mode=mode,
    )
    db.add(assignment)
    await db.flush()  # need assignment.id for the child rows below

    for order_index, (question_id, marks) in enumerate(questions):
        db.add(
            AssignmentQuestion(
                assignment_id=assignment.id,
                question_id=question_id,
                order_index=order_index,
                marks=marks,
            )
        )
    for learner_id in learner_ids:
        db.add(AssignmentTarget(assignment_id=assignment.id, learner_id=learner_id))

    return assignment


async def release_assignment_results(db: AsyncSession, *, assignment: Assignment) -> Assignment:
    """
    Flips the one-way switch (ADR-029) that reveals a Test-mode
    assignment's withheld is_correct/ai_feedback/marks_earned to every
    targeted student. Deliberately takes the already-fetched, already
    ownership-checked Assignment row rather than an id -- the router
    (app/routers/teach_assignments.py) owns the "does this assignment
    belong to this teacher" check, same split as everywhere else in
    this module; this function only ever flips the flag. Idempotent --
    releasing an already-released assignment is a no-op, not an error,
    since there's no harm in a teacher clicking it twice.
    """
    assignment.results_released = True
    db.add(assignment)
    return assignment


async def list_bank_questions_for_topic(
    db: AsyncSession, *, teacher: User, topic_id: uuid.UUID
) -> list[Question]:
    """
    Questions a teacher can reuse in a new assignment for this topic
    (ADR-029's "derive some from the textbook, create some yourself"
    request): every seeded/CAPS-bank question for the topic
    (created_by_user_id is None) plus this teacher's own previously-
    authored custom questions for it -- never another teacher's custom
    question, which is private to the assignments they build. Ordered
    oldest-first, same convention as the rest of this module.
    """
    stmt = (
        select(Question)
        .where(
            Question.topic_id == topic_id,
            (Question.created_by_user_id.is_(None)) | (Question.created_by_user_id == teacher.id),
        )
        .order_by(Question.created_at)
    )
    return (await db.execute(stmt)).scalars().all()


async def submit_assignment_answer(
    db: AsyncSession,
    tutor_client: TutorClient,
    *,
    learner: Learner,
    assignment_id: uuid.UUID,
    question_id: uuid.UUID,
    learner_response: str,
) -> tuple[Attempt, int]:
    """
    The real "submit -> mark -> write Attempt" flow ADR-028 names as
    this feature's actual architectural payload (see that ADR's
    Context section). Re-validates, server-side, that this learner was
    actually targeted for this assignment AND that this question
    actually belongs to it -- a learner's own client only ever shows
    what it was told to show, but that's not the boundary (same
    principle as create_assignment()'s learner_ids check above,
    applied here on the submit side).

    The real is_correct/ai_feedback are ALWAYS computed and written to
    Attempt here, test-mode or not (ADR-029) -- only the router decides
    whether to show them to the student, based on Assignment.mode and
    results_released. Returns (attempt, marks) -- marks is this
    question's point value in this assignment, read off the
    AssignmentQuestion row already fetched below so the router doesn't
    need a second query just to report it back in AnswerSubmitResult.
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
    assignment = await db.get(Assignment, assignment_id)
    reason = answers_closed_reason(assignment) if assignment is not None else None
    if reason:
        raise AssignmentClosed(reason)

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
    return attempt, in_assignment.marks


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
    # NEW (ADR-029). Sum of marks for every question whose LATEST
    # attempt is correct; marks_total is this assignment's full point
    # value, independent of how much this student has answered.
    marks_earned: int
    marks_total: int


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

    FIX (ADR-029 live-test finding): a student can resubmit a question
    via AssignmentsView.jsx's "Re-submit answer" button, which writes
    a SECOND Attempt row rather than updating the first (Attempt rows
    are append-only everywhere else in this app too). The original
    version of this function summed is_correct across every attempt
    row, so a student who got a question wrong, then resubmitted and
    got it right, could be double-counted or (if the wrong attempt
    sorted after the right one) under-counted. Attempts are now
    queried in created_at order and reduced to the LATEST attempt per
    question_id before counting -- one attempt's outcome per question,
    always the most recent one, matching what the student actually
    sees as "answered" in AssignmentsView.jsx.
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
    marks_by_question_id = {aq.question_id: aq.marks for aq in assignment_questions}
    marks_total = sum(marks_by_question_id.values())

    results: list[LearnerCompletion] = []
    for target in targets:
        attempts = (
            (
                await db.execute(
                    select(Attempt)
                    .where(
                        Attempt.assignment_id == assignment_id,
                        Attempt.learner_id == target.learner_id,
                    )
                    .order_by(Attempt.created_at)
                )
            )
            .scalars()
            .all()
        )
        # Overwriting in created_at order leaves the LATEST attempt per
        # question_id -- see the fix note above.
        latest_by_question: dict[uuid.UUID, Attempt] = {}
        for attempt in attempts:
            latest_by_question[attempt.question_id] = attempt

        answered_question_ids = set(latest_by_question.keys())
        correct_count = sum(
            1 for a in latest_by_question.values() if a.is_correct is True
        )
        marks_earned = sum(
            marks_by_question_id.get(qid, 0)
            for qid, a in latest_by_question.items()
            if a.is_correct is True
        )
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
                marks_earned=marks_earned,
                marks_total=marks_total,
            )
        )
    return results
