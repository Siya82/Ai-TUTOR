"""
GET /topics -- lists every seeded topic, for the frontend's topic picker.

NEW 8 Nov 2026, part of step 7. See app/schemas/topics.py for why this
exists: it replaces the recovered api.js's hardcoded, stale TOPIC_IDS
map with a real, always-current list straight from the database.
"""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models import Topic
from app.schemas.topics import TopicResponse

router = APIRouter(prefix="/topics", tags=["topics"])


@router.get("/", response_model=list[TopicResponse])
async def list_topics(
    subject_id: uuid.UUID | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> list[Topic]:
    """
    Topics, ordered by their CAPS term order within each subject, optionally
    filtered to one subject.

    FIX 12 Nov 2026 (multi-subject support, ADR-013): added the optional
    subject_id filter now that a second subject (Physical Sciences) is
    seeded alongside Pure Mathematics -- an unfiltered call still returns
    every topic across every subject (the frontend's own subject picker
    does the filtering for the UI; this param exists for any caller that
    wants it server-side instead).

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
    """
    stmt = select(Topic).order_by(Topic.subject_id, Topic.order_index)
    if subject_id is not None:
        stmt = stmt.where(Topic.subject_id == subject_id)
    result = await db.execute(stmt)
    return list(result.scalars().all())
