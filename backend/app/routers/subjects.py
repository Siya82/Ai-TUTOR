"""
GET /subjects -- lists every seeded subject, for the frontend's subject
picker.

NEW 12 Nov 2026, part of multi-subject support (ADR-013). See
app/schemas/subjects.py for why this exists now and didn't before.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models import Subject
from app.schemas.subjects import SubjectResponse

router = APIRouter(prefix="/subjects", tags=["subjects"])


@router.get("/", response_model=list[SubjectResponse])
async def list_subjects(db: AsyncSession = Depends(get_db)) -> list[Subject]:
    """All subjects, ordered by name then grade. No auth yet -- same documented
    caveat as /topics and /learners.

    FIX 13 Nov 2026 (Grade 11 added, ADR-014): name-only ordering gave no
    guaranteed, stable order between two rows sharing a name (e.g. "Pure
    Mathematics" grade 10 and grade 11) -- added grade as a secondary sort
    key so the frontend's default-subject pick and the picker's own listed
    order are both deterministic, not incidentally-whatever-Postgres-returned."""
    result = await db.execute(select(Subject).order_by(Subject.name, Subject.grade))
    return list(result.scalars().all())
