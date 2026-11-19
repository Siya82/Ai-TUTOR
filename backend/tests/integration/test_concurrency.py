"""deep scan H3: a class asking at once must not queue behind held database
connections. 40 learners ask together while the AI takes 2 s; with
connections released during the AI call, everyone is answered in about
2 s. (Before the fix, with 15 connections held for the whole call, the
slowest learner waited about 3x as long.)"""

import asyncio
import time
import uuid

import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.routers.tutor as tutor_router
from app.core.database import get_db
from app.main import app
from app.models import Learner, School, Subject, Topic, TutorMessage, User
from tests.integration.conftest import TEST_DB, _migrate, auth


@pytest.fixture
async def pooled():
    """The real pooled engine (not NullPool), with only 15 connections."""
    _migrate()
    engine = create_async_engine(TEST_DB, pool_size=5, max_overflow=10, pool_timeout=30)
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def _get_db():
        async with maker() as s:
            yield s

    app.dependency_overrides[get_db] = _get_db
    yield maker
    app.dependency_overrides.pop(get_db, None)
    await engine.dispose()


async def test_forty_learners_at_once(pooled, monkeypatch):
    async def slow_ai(system, messages, max_tokens=None, **kwargs):
        await asyncio.sleep(2)
        return "Here's a hint."

    monkeypatch.setattr(tutor_router._tutor_client, "ask", slow_ai)
    tag = uuid.uuid4().hex[:6]
    async with pooled() as db:
        school = School(name=f"Busy School {tag}")
        subject = Subject(name=f"Busy Maths {tag}", grade=10)
        db.add_all([school, subject])
        await db.flush()
        topic = Topic(subject_id=subject.id, name="Exponents")
        db.add(topic)
        users = []
        for i in range(40):
            u = User(role="student", school_id=school.id, student_number=f"B{i}", password_hash="x",
                     must_change_password=False)
            db.add(u)
            await db.flush()
            db.add(Learner(display_name=f"L{i}", grade=10, user_id=u.id))
            users.append(u)
        await db.commit()

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t", timeout=120) as c:
        async def ask(u):
            t = time.monotonic()
            r = await c.post("/tutor/message", headers=auth(u), json={"message": "help", "topic_id": str(topic.id)})
            return r.status_code, time.monotonic() - t

        results = await asyncio.gather(*(ask(u) for u in users))
    assert all(code == 200 for code, _ in results)
    slowest = max(t for _, t in results)
    assert slowest < 5, f"slowest learner waited {slowest:.1f}s"


async def test_failed_ai_call_leaves_no_orphan_question(client, world, sessionmaker, monkeypatch):
    async def broken(*a, **k):
        raise RuntimeError("AI down")

    monkeypatch.setattr(tutor_router._tutor_client, "ask", broken)
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)  # see the 500 like a browser would
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as raw:
        r = await raw.post("/tutor/message", headers=world.h("a1"),
                           json={"message": "help", "topic_id": str(world.topic.id)})
    assert r.status_code >= 500
    from sqlalchemy import func, select

    from app.models import TutorSession

    async with sessionmaker() as db:
        n = (
            await db.execute(
                select(func.count()).select_from(TutorMessage).join(TutorSession)
                .where(TutorSession.learner_id == world.learners["a1"].id)
            )
        ).scalar_one()
    assert n == 0
    assert (await client.get("/tutor/usage", headers=world.h("a1"))).json()["used_today"] == 0
