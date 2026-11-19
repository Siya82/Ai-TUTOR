"""deep scan M1: the nightly clean-up deletes only what it should."""

from datetime import timedelta

from sqlalchemy import func, select

import scripts.retention as retention
from app.core.clock import utcnow_naive
from app.models import RateEvent, TutorMessage, TutorSession


async def test_retention_respects_periods(world, sessionmaker, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(retention, "async_session_factory", sessionmaker)
    old = utcnow_naive() - timedelta(days=400)
    async with sessionmaker() as db:
        db.add(RateEvent(key="test:old", created_at=utcnow_naive() - timedelta(days=5)))
        stale = TutorSession(learner_id=world.learners["a1"].id, topic_id=world.topic.id, created_at=old)
        live = TutorSession(learner_id=world.learners["a2"].id, topic_id=world.topic.id, created_at=old)
        db.add_all([stale, live])
        await db.flush()
        db.add(TutorMessage(session_id=stale.id, role="user", content="old question", created_at=old))
        db.add(TutorMessage(session_id=live.id, role="user", content="asked today"))  # still in use
        await db.commit()

    monkeypatch.setattr(settings, "retention_conversation_days", 0)
    dry = await retention.run(dry_run=False)
    assert "conversations" not in dry  # 0 = keep: nothing touched
    async with sessionmaker() as db:
        assert await db.get(TutorSession, stale.id) is not None
        assert (await db.execute(select(func.count()).select_from(RateEvent).where(RateEvent.key == "test:old"))).scalar_one() == 0

    monkeypatch.setattr(settings, "retention_conversation_days", 365)
    counts = await retention.run(dry_run=False)
    assert counts["conversations"] >= 1
    async with sessionmaker() as db:
        assert await db.get(TutorSession, stale.id) is None
        assert await db.get(TutorSession, live.id) is not None  # a conversation in use is kept
