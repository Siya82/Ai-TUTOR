"""
Teacher-only admin API: single and bulk student provisioning, and the
school's student roster -- the real replacement for "re-run
scripts/seed_dev_data.py directly" as the only way to add a student, a
gap this project's own report/BUILD_LOG flagged as open since ADR-017.
See docs/ADR-024-teacher-dashboard-and-provisioning.md.

NEW 15 Nov 2026.
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_teacher
from app.models import Learner, School, User
from app.schemas.admin import (
    BulkStudentRowError,
    BulkStudentUploadResponse,
    StudentCreateRequest,
    StudentCreateResult,
    StudentRosterItem,
)
from app.services.admin import bulk_provision_students, parse_student_csv
from app.services.auth import provision_student

router = APIRouter(prefix="/admin", tags=["admin"])


async def _teacher_school(db: AsyncSession, teacher: User) -> School:
    school = await db.get(School, teacher.school_id)
    if school is None:
        # Should be unreachable -- School.id is a required FK on User --
        # but fail loudly if it's ever wrong rather than silently 404ing.
        raise HTTPException(status_code=500, detail="Teacher account has no linked school")
    return school


@router.post("/students", response_model=StudentCreateResult)
async def create_student(
    payload: StudentCreateRequest,
    teacher: User = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
) -> StudentCreateResult:
    """Provisions one student in the authenticated teacher's own school."""
    school = await _teacher_school(db, teacher)
    try:
        user, learner, temp_password = await provision_student(
            db,
            school=school,
            display_name=payload.display_name,
            grade=payload.grade,
            student_number=payload.student_number,
        )
    except RuntimeError as exc:
        # provision_student's own "couldn't generate a unique number"
        # failure, or (indirectly, via a DB constraint a caller-supplied
        # student_number violates) a collision -- either way this is the
        # teacher's input to fix, not a server error.
        raise HTTPException(status_code=400, detail=str(exc))
    await db.commit()
    return StudentCreateResult(
        user_id=user.id,
        learner_id=learner.id,
        display_name=learner.display_name,
        grade=learner.grade,
        student_number=user.student_number,
        temp_password=temp_password,
    )


@router.post("/students/bulk", response_model=BulkStudentUploadResponse)
async def bulk_create_students(
    file: UploadFile,
    teacher: User = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
) -> BulkStudentUploadResponse:
    """
    Provisions many students at once from a teacher-uploaded CSV
    (columns: display_name, grade, optional student_number). Rows that
    fail to parse, or fail to provision, are reported individually in
    `errors` rather than aborting rows that succeeded.
    """
    school = await _teacher_school(db, teacher)
    raw = await file.read()
    try:
        # utf-8-sig strips an Excel-exported CSV's byte-order mark, which
        # would otherwise land inside the first column's header name and
        # make display_name look "missing" even when it's right there.
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="CSV file must be UTF-8 encoded")

    parsed = parse_student_csv(text)
    if not parsed.rows and parsed.errors:
        # A structural problem (missing columns, empty file) -- nothing
        # here is a per-row issue, so this is a 400, not a 200 with an
        # empty created[] and one error in the list.
        raise HTTPException(status_code=400, detail=parsed.errors[0][1])

    created, row_errors = await bulk_provision_students(db, school=school, rows=parsed.rows)
    if created:
        await db.commit()

    all_errors = [BulkStudentRowError(row=r, message=m) for r, m in parsed.errors + row_errors]
    return BulkStudentUploadResponse(
        created=[StudentCreateResult(**c) for c in created],
        errors=all_errors,
    )


@router.get("/students", response_model=list[StudentRosterItem])
async def list_students(
    teacher: User = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
) -> list[StudentRosterItem]:
    """
    This teacher's own school's students only -- joins through User
    rather than listing every Learner, so a Learner seeded without a
    linked User (old dev data from before ADR-017) correctly doesn't
    appear here, matching the scoping app/routers/dashboard.py now
    applies for the same reason.
    """
    stmt = (
        select(Learner, User)
        .join(User, Learner.user_id == User.id)
        .where(User.school_id == teacher.school_id, User.role == "student")
        .order_by(Learner.display_name)
    )
    result = await db.execute(stmt)
    return [
        StudentRosterItem(
            learner_id=learner.id,
            user_id=user.id,
            display_name=learner.display_name,
            grade=learner.grade,
            student_number=user.student_number,
            created_at=user.created_at,
        )
        for learner, user in result.all()
    ]
