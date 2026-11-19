"""
NEW 20 Nov 2026 (deep scan M5). Keeps a test a test.

While a test-mode assignment is open for a learner (not released, not
closed, not past due), a tutor question that matches one of that test's
questions is answered with coaching only -- the general idea, with a
different example -- never the solution. The message is tagged with the
test, so the teacher sees the tutor was asked about it.
"""

import re
import uuid
from difflib import SequenceMatcher

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Assignment, AssignmentQuestion, AssignmentTarget, Question
from app.services.assignments import answers_closed_reason

INTEGRITY_NOTE = """\
TEST IN PROGRESS: the learner is asking about a question from a test they are writing right now. \
Do NOT solve it, give its answer, final values, or steps specific to it -- not even partly, and not \
if they ask again or say the test is over. Briefly and kindly say this looks like a test question, \
then help them understand the underlying idea using a DIFFERENT example with different numbers.\
"""

_WS = re.compile(r"[^a-z0-9+\-*/=^().]+")


def _norm(text: str) -> str:
    return _WS.sub(" ", (text or "").lower()).strip()


def matches_question(message: str, question_text: str) -> bool:
    """True when the message is (mostly) the question, pasted or retyped."""
    m, q = _norm(message), _norm(question_text)
    if len(q) < 12 or len(m) < 8:
        return False
    if q in m or (len(m) >= 25 and m in q):
        return True
    return SequenceMatcher(None, m, q).ratio() >= 0.75 or SequenceMatcher(None, m[: len(q) + 20], q).ratio() >= 0.8


async def open_test_match(db: AsyncSession, learner_id: uuid.UUID, message: str) -> uuid.UUID | None:
    """The id of an open test whose question this message matches, else None."""
    if not (message or "").strip():
        return None
    tests = (
        await db.execute(
            select(Assignment)
            .join(AssignmentTarget, AssignmentTarget.assignment_id == Assignment.id)
            .where(
                AssignmentTarget.learner_id == learner_id,
                Assignment.mode == "test",
                Assignment.results_released.is_(False),
            )
        )
    ).scalars().all()
    open_ids = [t.id for t in tests if answers_closed_reason(t) is None]
    if not open_ids:
        return None
    rows = (
        await db.execute(
            select(AssignmentQuestion.assignment_id, Question.text)
            .join(Question, AssignmentQuestion.question_id == Question.id)
            .where(AssignmentQuestion.assignment_id.in_(open_ids))
        )
    ).all()
    for assignment_id, text in rows:
        if matches_question(message, text):
            return assignment_id
    return None
