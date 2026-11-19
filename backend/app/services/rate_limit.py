"""
NEW 20 Nov 2026 (deep scan L6). Rate limits counted in the database, so they
hold across server processes and restarts.

    if await rate_limit.too_many(db, "redeem:ip:1.2.3.4", limit=10, window=3600):
        raise HTTPException(429, ...)
    await rate_limit.hit(db, "redeem:ip:1.2.3.4")

`hit` adds a row to the caller's session (committed with the request).
"""

from datetime import datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utcnow_naive
from app.models import RateEvent


async def count(db: AsyncSession, key: str, window_seconds: int, now: datetime | None = None) -> int:
    since = (now or utcnow_naive()) - timedelta(seconds=window_seconds)
    return (
        await db.execute(
            select(func.count()).select_from(RateEvent).where(RateEvent.key == key, RateEvent.created_at >= since)
        )
    ).scalar_one()


async def oldest_in_window(db: AsyncSession, key: str, window_seconds: int, now: datetime | None = None):
    since = (now or utcnow_naive()) - timedelta(seconds=window_seconds)
    return (
        await db.execute(
            select(func.min(RateEvent.created_at)).where(RateEvent.key == key, RateEvent.created_at >= since)
        )
    ).scalar_one()


async def too_many(db: AsyncSession, key: str, limit: int, window_seconds: int) -> bool:
    return await count(db, key, window_seconds) >= limit


async def hit(db: AsyncSession, key: str) -> None:
    db.add(RateEvent(key=key[:200]))


async def clear(db: AsyncSession, key: str) -> None:
    await db.execute(delete(RateEvent).where(RateEvent.key == key))
