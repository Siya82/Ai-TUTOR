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
    Topics, ordered by name, optionally filtered to one subject.

    FIX 12 Nov 2026 (multi-subject support, ADR-013): added the optional
    subject_id filter now that a second subject (Physical Sciences) is
    seeded alongside Pure Mathematics -- an unfiltered call still returns
    every topic across every subject (the frontend's own subject picker
    does the filtering for the UI; this param exists for any caller that
    wants it server-side instead).
    """
    stmt = select(Topic).order_by(Topic.name)
    if subject_id is not None:
        stmt = stmt.where(Topic.subject_id == subject_id)
    result = await db.execute(stmt)
    return list(result.scalars().all())
