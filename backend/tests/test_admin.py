"""
Tests for the teacher-admin feature (ADR-024, teacher dashboard access +
bulk student provisioning). Pure -- no DB, no network, no FastAPI app,
matching every other service test in this project (test_auth.py,
test_attachments.py, ...).

Covered here: app/services/admin.py's parse_student_csv() (the pure
CSV-parsing half of the bulk-upload path -- bulk_provision_students()
itself needs a real AsyncSession for its uniqueness-checking queries,
same "integration, not unit" line test_auth.py already draws around
provision_student()) and app/core/security.py's get_current_teacher()
(role-check logic that's DB-free once it's handed a User instance --
it never queries anything itself).

NOTE for whoever runs this file: same as test_auth.py, importing
app.core.config (via app.models -> ... -> app.core.security) requires
JWT_SECRET_KEY (and the other required settings) in backend/.env.
"""

import uuid

import pytest
from fastapi import HTTPException

from app.core.security import get_current_teacher
from app.models import User
from app.services.admin import parse_student_csv


# ---------------------------------------------------------------------------
# parse_student_csv
# ---------------------------------------------------------------------------


def test_parse_student_csv_happy_path():
    csv_text = "display_name,grade,student_number\nThandiwe Khumalo,10,100042\nSipho Ndlovu,11,\n"
    result = parse_student_csv(csv_text)
    assert result.errors == []
    assert len(result.rows) == 2
    assert result.rows[0].display_name == "Thandiwe Khumalo"
    assert result.rows[0].grade == 10
    assert result.rows[0].student_number == "100042"
    # A blank student_number column means "auto-generate", same as the
    # column being omitted entirely -- never an empty string sent on to
    # provision_student().
    assert result.rows[1].student_number is None


def test_parse_student_csv_student_number_column_is_optional():
    csv_text = "display_name,grade\nLerato Mokoena,12\n"
    result = parse_student_csv(csv_text)
    assert result.errors == []
    assert len(result.rows) == 1
    assert result.rows[0].student_number is None


def test_parse_student_csv_missing_required_column_fails_the_whole_file():
    csv_text = "name,grade\nLerato Mokoena,12\n"
    result = parse_student_csv(csv_text)
    assert result.rows == []
    assert len(result.errors) == 1
    row_number, message = result.errors[0]
    assert row_number == 0  # a whole-file problem, not one row
    assert "display_name" in message


def test_parse_student_csv_empty_file_fails_cleanly():
    result = parse_student_csv("")
    assert result.rows == []
    assert len(result.errors) == 1
    assert result.errors[0][0] == 0


def test_parse_student_csv_blank_display_name_is_a_row_error_not_a_crash():
    csv_text = "display_name,grade\n,10\nReal Name,11\n"
    result = parse_student_csv(csv_text)
    # Row 2 (the blank one) is reported; row 3 (valid) still comes through --
    # one bad row must not sink the rest of the file.
    assert len(result.rows) == 1
    assert result.rows[0].display_name == "Real Name"
    assert len(result.errors) == 1
    assert result.errors[0][0] == 2
    assert "display_name" in result.errors[0][1]


def test_parse_student_csv_non_numeric_grade_is_a_row_error_not_a_crash():
    csv_text = "display_name,grade\nThandiwe Khumalo,ten\n"
    result = parse_student_csv(csv_text)
    assert result.rows == []
    assert len(result.errors) == 1
    row_number, message = result.errors[0]
    assert row_number == 2
    assert "grade" in message


def test_parse_student_csv_ignores_extra_columns():
    # A teacher's own export from a school admin system may carry more
    # columns than THUTOra needs (email, home address, ...) -- these
    # should be silently ignored, not treated as an error.
    csv_text = "display_name,grade,email,student_number\nThandiwe Khumalo,10,t@example.com,100042\n"
    result = parse_student_csv(csv_text)
    assert result.errors == []
    assert len(result.rows) == 1
    assert result.rows[0].student_number == "100042"


# ---------------------------------------------------------------------------
# get_current_teacher
# ---------------------------------------------------------------------------


def _bare_user(role: str) -> User:
    """A User instance with no DB session -- fine for a role-check test,
    since get_current_teacher() never queries anything itself."""
    return User(
        id=uuid.uuid4(),
        role=role,
        school_id=uuid.uuid4(),
        student_number="100001",
        password_hash="irrelevant-for-this-test",
    )


@pytest.mark.asyncio
async def test_get_current_teacher_allows_a_teacher_role_user():
    teacher = _bare_user("teacher")
    result = await get_current_teacher(user=teacher)
    assert result is teacher


@pytest.mark.asyncio
async def test_get_current_teacher_rejects_a_student_role_user():
    student = _bare_user("student")
    with pytest.raises(HTTPException) as exc_info:
        await get_current_teacher(user=student)
    assert exc_info.value.status_code == 403
