"""
GET /topics -- lists every seeded topic the CURRENT STUDENT is allowed
to see, for the frontend's topic picker.

NEW 8 Nov 2026, part of step 7. See app/schemas/topics.py for why this
exists: it replaces the recovered api.js's hardcoded, stale TOPIC_IDS
map with a real, always-current list straight from the database.
"""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_learner
from app.models import Learner, Subject, Topic
from app.schemas.topics import TopicResponse

router = APIRouter(prefix="/topics", tags=["topics"])


@router.get("/", response_model=list[TopicResponse])
async def list_topics(
    subject_id: uuid.UUID | None = Query(default=None),
    learner: Learner = Depends(get_current_learner),
    db: AsyncSession = Depends(get_db),
) -> list[Topic]:
    """
    Topics at or below the current learner's own grade, ordered by
    their CAPS term order within each subject, optionally filtered to
    one subject.

    FIX 12 Nov 2026 (multi-subject support, ADR-013): added the optional
    subject_id filter now that a second subject (Physical Sciences) is
    seeded alongside Pure Mathematics -- an unfiltered call still returns
    every topic across every subject the learner is allowed to see.

    FIX 15 Nov 2026 (live-test finding): was ordering by Topic.name
    (alphabetical), which scrambled the real CAPS teaching order a
    student sees in the sidebar -- e.g. "Algebraic Expressions" sorted
    after "Analytical Geometry" purely alphabetically, even though
    Algebraic Expressions is the Term 1 foundation and Analytical
    Geometry comes much later. Now orders by order_index, each topic's
    position in seed_dev_data.py's own topic list for that subject
    (which follows the real DBE ATP term order -- see that file's
    per-subject lists), with subject_id as the primary sort key so an
    unfiltered call still groups each subject's topics together.

    FIX 15 Nov 2026, continued (grade-scoped visibility, ADR-026): same
    gap as /subjects -- this endpoint used to return every topic across
    every grade to anyone, auth or no auth. Now requires a logged-in
    learner and joins to Subject to exclude any topic belonging to a
    grade above the learner's own, matching /subjects' new scoping
    exactly (a student should never be able to browse, let alone be
    taught, content from a grade they haven't reached yet).
    """
    stmt = (
        select(Topic)
        .join(Subject, Topic.subject_id == Subject.id)
        .where(Subject.grade <= learner.grade)
        .order_by(Topic.subject_id, Topic.order_index)
    )
    if subject_id is not None:
        stmt = stmt.where(Topic.subject_id == subject_id)
    result = await db.execute(stmt)
    return list(result.scalars().all())
