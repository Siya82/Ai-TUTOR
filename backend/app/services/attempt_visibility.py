"""
NEW 19 Nov 2026 (code review 19 Nov #1). Which marked attempts may be shown
to the learner and their family.

A test-mode assignment withholds marks until the teacher releases them
(ADR-029). Any view that turns attempts into percentages or topic
strengths (CONNECT's overview and weekly summary, the learner's own
"My progress") must leave those answers out too, or the percentages give
the result away early. Practice answers and tutor-chat checks always count.
"""

from sqlalchemy import or_, select

from app.models import Assignment, Attempt


def released_attempts_only():
    """A WHERE clause on Attempt: not part of an unreleased test."""
    unreleased_test = (
        select(Assignment.id)
        .where(Assignment.mode == "test", Assignment.results_released.is_(False))
        .scalar_subquery()
    )
    return or_(Attempt.assignment_id.is_(None), Attempt.assignment_id.not_in(unreleased_test))


