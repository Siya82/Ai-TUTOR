"""
GET /topics -- lists every seeded topic, for the frontend's topic picker.

NEW 8 Nov 2026, part of step 7. See app/schemas/topics.py for why this
exists: it replaces the recovered api.js's hardcoded, stale TOPIC_IDS
map with a real, always-current list straight from the database.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models import Topic
from app.schemas.topics import TopicResponse

router = APIRouter(prefix="/topics", tags=["topics"])


@router.get("/", response_model=list[TopicResponse])
async def list_topics(db: AsyncSession = Depends(get_db)) -> list[Topic]:
    """
    All topics across all subjects, ordered by name. There is currently
    only one seeded subject (Pure Mathematics, grade 10), so this is not
    yet subject-filtered -- revisit if/when a second subject is seeded
    (see REBUILD_SPEC.md's own note on the broader multi-subject THUTOra
    brand vision vs. the current Maths-only engineering scope, ADR-006).
    """
    result = await db.execute(select(Topic).order_by(Topic.name))
    return list(result.scalars().all())
