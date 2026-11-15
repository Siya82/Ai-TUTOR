"""
GET /subjects -- lists every seeded subject the CURRENT STUDENT is
allowed to see, for the frontend's subject picker.

NEW 12 Nov 2026, part of multi-subject support (ADR-013). See
app/schemas/subjects.py for why this exists now and didn't before.

FIX 15 Nov 2026 (grade-scoped visibility, ADR-026): Siya flagged that
once THUTOra is live, a student should only ever be able to SEE (let
alone pick) subjects for their own grade and grades below it -- never
a grade ahead. This endpoint previously returned every subject at
every grade, unfiltered, to anyone, auth or no auth. Now requires a
logged-in learner (closing the "No auth yet" gap this endpoint carried
since 12 Nov 2026) and filters to Subject.grade <= learner.grade. The
learner's own grade (set at provisioning, not client-supplied) is the
one source of truth for this -- there is deliberately no way for the
request to ask for a different grade's subjects.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_learner_or_teacher
from app.models import Learner, Subject, User
from app.schemas.subjects import SubjectResponse

router = APIRouter(prefix="/subjects", tags=["subjects"])


@router.get("/", response_model=list[SubjectResponse])
async def list_subjects(
    identity: tuple[User, Learner | None] = Depends(get_current_learner_or_teacher),
    db: AsyncSession = Depends(get_db),
) -> list[Subject]:
    """Every subject at or below the current learner's own grade,
    ordered by name then grade. A teacher instead sees every subject,
    unfiltered -- see get_current_learner_or_teacher's docstring
    (live-test finding, 15 Nov 2026, follow-up to ADR-026/ADR-028).

    FIX 13 Nov 2026 (Grade 11 added, ADR-014): name-only ordering gave no
    guaranteed, stable order between two rows sharing a name (e.g. "Pure
    Mathematics" grade 10 and grade 11) -- added grade as a secondary sort
    key so the frontend's default-subject pick and the picker's own listed
    order are both deterministic, not incidentally-whatever-Postgres-returned.
    """
    _, learner = identity
    stmt = select(Subject).order_by(Subject.name, Subject.grade)
    if learner is not None:
        # A real student: unchanged ADR-026 grade scoping. A teacher
        # (learner is None) sees every subject, unfiltered -- same
        # live-test-driven fix as /topics, see get_current_learner_or_teacher.
        stmt = stmt.where(Subject.grade <= learner.grade)
    result = await db.execute(stmt)
    return list(result.scalars().all())
