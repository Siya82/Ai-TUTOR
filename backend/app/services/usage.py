"""
NEW 19 Nov 2026 (code review 19 Nov #3). How many tutor questions a learner
has asked today, against settings.tutor_daily_limit. "Today" is the South
African day (UTC+2, no daylight saving), since that's when a learner's day
resets -- not midnight UTC, which is 02:00 here.
"""

import uuid
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utcnow_naive
from app.core.config import settings
from app.models import TutorMessage, TutorSession

SAST = timedelta(hours=2)


def start_of_sa_day(now_utc: datetime) -> datetime:
    """Naive-UTC timestamp of the most recent 00:00 in South Africa."""
    local = now_utc + SAST
    return local.replace(hour=0, minute=0, second=0, microsecond=0) - SAST


async def questions_today(db: AsyncSession, learner_id: uuid.UUID, now: datetime | None = None) -> int:
    since = start_of_sa_day(now or utcnow_naive())
    return (
        await db.execute(
            select(func.count())
            .select_from(TutorMessage)
            .join(TutorSession, TutorMessage.session_id == TutorSession.id)
            .where(
                TutorSession.learner_id == learner_id,
                TutorMessage.role == "user",
                TutorMessage.created_at >= since,
            )
        )
    ).scalar_one()


def remaining(used: int, limit: int | None = None) -> int | None:
    limit = settings.tutor_daily_limit if limit is None else limit
    return None if limit <= 0 else max(limit - used, 0)
