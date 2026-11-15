"""
Tests for the Assignments feature's service layer (ADR-028).

Covered here: app/services/assignments.py's create_custom_question()
-- the one function in that module that's pure (no DB access, builds
and returns a Question instance for the caller to add/commit), same
split test_admin.py documents for parse_student_csv() vs
bulk_provision_students().

NOT covered here: create_assignment(), submit_assignment_answer(), and
get_assignment_completion() -- all three need a real AsyncSession for
their scoping/existence queries, same "integration, not unit" line
test_admin.py's own docstring draws around bulk_provision_students()
and test_auth.py draws around provision_student(). Exercised instead
via this project's "ship then verify against real testing" discipline
once this feature is live-tested end to end (see ADR-028's Open Items).

NOTE for whoever runs this file: same as test_admin.py/test_auth.py,
importing app.core.config (via app.models -> ... -> app.core.security)
requires JWT_SECRET_KEY (and the other required settings) in
backend/.env.
"""

import uuid

from app.services.assignments import create_custom_question


class _FakeTeacher:
    """A bare stand-in for a User row -- create_custom_question() only
    ever reads .id off it, so a real DB-backed User is unnecessary here."""

    def __init__(self):
        self.id = uuid.uuid4()


def test_create_custom_question_sets_authored_fields():
    teacher = _FakeTeacher()
    topic_id = uuid.uuid4()

    question = create_custom_question(
        teacher=teacher,
        topic_id=topic_id,
        text="Solve for x: 2x + 5 = 15",
        model_answer="x = 5",
    )

    assert question.topic_id == topic_id
    assert question.text == "Solve for x: 2x + 5 = 15"
    assert question.model_answer == "x = 5"
    # The actual point of this field (ADR-028): created_by_user_id is
    # what distinguishes a teacher-authored question from the seeded/
    # diagnostic/AI-generated bank -- never a separate boolean.
    assert question.created_by_user_id == teacher.id
    assert question.is_diagnostic is False
    assert question.is_ai_generated is False
