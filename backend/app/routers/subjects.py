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
    """All subjects, ordered by name. No auth yet -- same documented caveat as /topics and /learners."""
    result = await db.execute(select(Subject).order_by(Subject.name))
    return list(result.scalars().all())
