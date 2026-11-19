"""
Teacher-admin service logic: bulk student CSV parsing (pure, unit-
tested without a DB -- same split this project uses everywhere else,
e.g. app/services/attachments.py's save_upload) and the thin DB-
touching loop that turns parsed rows into real accounts via
provision_student(). See docs/ADR-024-teacher-dashboard-and-provisioning.md.

NEW 15 Nov 2026.
"""

import csv
import io
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import LearnerGuardian, School
from app.services.auth import provision_student
from app.services.family import normalize_sa_cellphone

REQUIRED_COLUMNS = {"display_name", "grade"}


@dataclass
class ParsedStudentRow:
    row_number: int  # 1-based CSV row as a teacher would see it in a spreadsheet (the header is row 1)
    display_name: str
    grade: int
    student_number: str | None
    # NEW 19 Nov 2026 (ADR-043): optional guardian contact columns --
    # guardian_name, guardian_relationship, guardian_cellphone, guardian_email.
    # The cellphone is what lets that parent sign themselves up later.
    guardian_name: str | None = None
    guardian_relationship: str | None = None
    guardian_cellphone: str | None = None  # normalised +27...
    guardian_email: str | None = None


@dataclass
class ParsedCsvResult:
    rows: list[ParsedStudentRow]
    errors: list[tuple[int, str]]  # (row_number, message); row_number 0 means "whole file", not one row


def parse_student_csv(content: str) -> ParsedCsvResult:
    """
    Parses a teacher-uploaded CSV of students. Expected columns:
    display_name, grade, and an optional student_number -- column
    order doesn't matter (csv.DictReader keys off the header row), and
    extra columns are ignored rather than rejected, since a teacher's
    own export from a school admin system may well carry more columns
    than THUTOra needs.

    Deliberately collects one error per bad row rather than raising on
    the first problem -- a teacher uploading 30 students shouldn't lose
    all 30 because row 17 has a typo'd grade; they can fix just that
    row and re-upload. No de-duplication is attempted against students
    already in the roster (by name or otherwise) -- re-uploading the
    same CSV twice creates two sets of accounts, which is a deliberate
    choice to not guess at what the teacher meant, not an oversight.
    """
    reader = csv.DictReader(io.StringIO(content))
    if reader.fieldnames is None:
        return ParsedCsvResult(rows=[], errors=[(0, "CSV file is empty or has no header row")])

    header = {h.strip() for h in reader.fieldnames if h}
    missing = REQUIRED_COLUMNS - header
    if missing:
        return ParsedCsvResult(
            rows=[],
            errors=[(0, f"CSV is missing required column(s): {', '.join(sorted(missing))}")],
        )

    rows: list[ParsedStudentRow] = []
    errors: list[tuple[int, str]] = []
    for i, raw_row in enumerate(reader, start=2):  # row 1 is the header
        display_name = (raw_row.get("display_name") or "").strip()
        grade_raw = (raw_row.get("grade") or "").strip()
        student_number = (raw_row.get("student_number") or "").strip() or None

        if not display_name:
            errors.append((i, "display_name is required"))
            continue
        try:
            grade = int(grade_raw)
        except ValueError:
            errors.append((i, f"grade must be a whole number, got {grade_raw!r}"))
            continue

        guardian_name = (raw_row.get("guardian_name") or "").strip() or None
        guardian_cell_raw = (raw_row.get("guardian_cellphone") or "").strip()
        guardian_cellphone = None
        if guardian_cell_raw:
            try:
                guardian_cellphone = normalize_sa_cellphone(guardian_cell_raw)
            except ValueError:
                errors.append((i, f"guardian_cellphone {guardian_cell_raw!r} isn't a South African cellphone number"))
                continue
        if (guardian_cellphone or raw_row.get("guardian_email")) and not guardian_name:
            errors.append((i, "guardian_name is required when a guardian cellphone or email is given"))
            continue

        rows.append(
            ParsedStudentRow(
                row_number=i,
                display_name=display_name,
                grade=grade,
                student_number=student_number,
                guardian_name=guardian_name,
                guardian_relationship=(raw_row.get("guardian_relationship") or "").strip() or None,
                guardian_cellphone=guardian_cellphone,
                guardian_email=(raw_row.get("guardian_email") or "").strip() or None,
            )
        )

    return ParsedCsvResult(rows=rows, errors=errors)


async def bulk_provision_students(
    db: AsyncSession, *, school: School, rows: list[ParsedStudentRow]
) -> tuple[list[dict], list[tuple[int, str]]]:
    """
    DB-touching loop over already-parsed rows -- kept thin and separate
    from parse_student_csv() on purpose (the same "pure logic vs. DB"
    split provision_student() itself follows), so this is the one part
    of the bulk-upload path that needs an integration test rather than
    a unit test. A per-row failure (most likely a caller-supplied
    student_number that collides within this school) is caught and
    reported against that one row rather than aborting rows that were
    already successfully created earlier in the same batch -- catching
    bare Exception is deliberate here for exactly that reason, not
    sloppiness.
    """
    created: list[dict] = []
    row_errors: list[tuple[int, str]] = []
    for row in rows:
        try:
            user, learner, temp_password = await provision_student(
                db,
                school=school,
                display_name=row.display_name,
                grade=row.grade,
                student_number=row.student_number,
            )
        except Exception as exc:  # noqa: BLE001 -- one bad row must not sink the whole batch
            row_errors.append((row.row_number, str(exc)))
            continue
        if row.guardian_name:  # ADR-043
            db.add(
                LearnerGuardian(
                    learner_id=learner.id,
                    full_name=row.guardian_name,
                    relationship_to_learner=row.guardian_relationship or "Parent",
                    cellphone=row.guardian_cellphone,
                    email=row.guardian_email,
                )
            )
        created.append(
            {
                "user_id": user.id,
                "learner_id": learner.id,
                "display_name": learner.display_name,
                "grade": learner.grade,
                "student_number": user.student_number,
                "temp_password": temp_password,
            }
        )
    return created, row_errors
