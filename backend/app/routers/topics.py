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
from app.core.security import get_current_learner_or_teacher
from app.models import Learner, Subject, Topic, User, VideoResource
from app.schemas.topics import TopicResponse

router = APIRouter(prefix="/topics", tags=["topics"])

THUTORA_VIDEO_SOURCE = "THUTOra"  # ADR-049: our own topic overviews


@router.get("/", response_model=list[TopicResponse])
async def list_topics(
    subject_id: uuid.UUID | None = Query(default=None),
    identity: tuple[User, Learner | None] = Depends(get_current_learner_or_teacher),
    db: AsyncSession = Depends(get_db),
) -> list[TopicResponse]:
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

    FIX 15 Nov 2026, continued again (live-test finding): the above
    broke the teacher-side topic picker (ADR-028's CreateAssignmentForm)
    the first time anyone actually tried it, since a teacher has no
    Learner row. Now depends on get_current_learner_or_teacher instead:
    a student still gets the exact grade filter above; a teacher gets
    every topic, unfiltered, since they may author a question for any
    grade they teach.
    """
    _, learner = identity
    stmt = (
        select(Topic)
        .join(Subject, Topic.subject_id == Subject.id)
        .order_by(Topic.subject_id, Topic.order_index)
    )
    if learner is not None:
        # A real student: unchanged ADR-026 grade scoping.
        stmt = stmt.where(Subject.grade <= learner.grade)
    # A teacher (learner is None): no grade filter -- see
    # get_current_learner_or_teacher's docstring for why.
    if subject_id is not None:
        stmt = stmt.where(Topic.subject_id == subject_id)
    topics = list((await db.execute(stmt)).scalars().all())
    # ADR-049: attach THUTOra's own overview video where one exists
    videos = {}
    if topics:
        rows = (
            await db.execute(
                select(VideoResource).where(
                    VideoResource.topic_id.in_([t.id for t in topics]),
                    VideoResource.source == THUTORA_VIDEO_SOURCE,
                )
            )
        ).scalars().all()
        videos = {v.topic_id: v for v in rows}
    out = []
    for t in topics:
        item = TopicResponse.model_validate(t)
        if v := videos.get(t.id):
            item.intro_video_url = v.url
            item.intro_video_seconds = v.duration_seconds
            item.intro_video_narrated = v.has_narration
        out.append(item)
    return out
