"""
NEW 19 Nov 2026 (code review 19 Nov #4): HTTP-level tests of who can see
and do what -- run through the real FastAPI app against a real Postgres.

These need their OWN database, so they never touch dev or production data:
set TEST_DATABASE_URL (CI points it at its throwaway database). Without it,
every test here is skipped. Locally, in PowerShell:

    createdb caps_tutor_test   # once; then in psql: CREATE EXTENSION vector;
    $env:TEST_DATABASE_URL = "postgresql+asyncpg://postgres:<pw>@localhost:5432/caps_tutor_test"
    python -m pytest tests/integration -q

Migrations are applied to that database automatically. Every test builds
its own school (unique names), so tests don't depend on each other or on
seed data, and nothing needs cleaning up between runs.
"""

import os
import subprocess
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import bcrypt
import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

TEST_DB = os.environ.get("TEST_DATABASE_URL")
if not TEST_DB:
    pytest.skip("TEST_DATABASE_URL not set -- skipping HTTP integration tests", allow_module_level=True)

BACKEND = Path(__file__).resolve().parents[2]
_migrated = False


def _migrate() -> None:
    global _migrated
    if _migrated:
        return
    env = {**os.environ, "DATABASE_URL": TEST_DB}
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=BACKEND, env=env, check=True,
                   capture_output=True)
    _migrated = True


# bcrypt at full cost makes each test take seconds; 4 rounds is plenty here.
_real_gensalt = bcrypt.gensalt
bcrypt.gensalt = lambda rounds=4, prefix=b"2b": _real_gensalt(4, prefix)

from app.core.database import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import (  # noqa: E402
    ClassMember,
    Learner,
    Question,
    School,
    SchoolClass,
    StaffRole,
    Subject,
    TeachingAllocation,
    Topic,
    User,
)
from app.services.auth import create_access_token, hash_password, provision_student, provision_teacher  # noqa: E402

PASSWORD = "TestPass123!"


@pytest.fixture
async def sessionmaker():
    _migrate()
    engine = create_async_engine(TEST_DB, poolclass=NullPool)
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def _get_db():
        async with maker() as s:
            yield s

    app.dependency_overrides[get_db] = _get_db
    yield maker
    app.dependency_overrides.pop(get_db, None)
    await engine.dispose()


@pytest.fixture
async def client(sessionmaker):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def auth(user: User) -> dict:
    return {"Authorization": f"Bearer {create_access_token(str(user.id), user.role, user.token_version or 0)}"}


@dataclass
class World:
    """One school: principal, two teachers (class A / class B), a school
    admin, learners in each class, a parent of learner a1, a subject/topic
    with questions. `h(name)` gives auth headers for any of them."""

    school: School
    subject: Subject
    topic: Topic
    questions: list[Question]
    users: dict[str, User] = field(default_factory=dict)
    learners: dict[str, Learner] = field(default_factory=dict)
    classes: dict[str, SchoolClass] = field(default_factory=dict)

    def h(self, name: str) -> dict:
        return auth(self.users[name])


@pytest.fixture
async def world(sessionmaker) -> World:
    tag = uuid.uuid4().hex[:8]
    async with sessionmaker() as db:
        school = School(name=f"Test School {tag}")
        db.add(school)
        subject = Subject(name=f"Test Maths {tag}", grade=10)
        db.add(subject)
        await db.flush()
        topic = Topic(subject_id=subject.id, name="Algebraic Expressions")
        db.add(topic)
        await db.flush()
        questions = [Question(topic_id=topic.id, text=f"Q{i}: simplify {i}x + x", model_answer=f"{i + 1}x")
                     for i in range(3)]
        db.add_all(questions)
        w = World(school=school, subject=subject, topic=topic, questions=questions)

        for name, role in (("principal", "principal"), ("admin", "school_admin"), ("teacher_a", None),
                           ("teacher_b", None)):
            user, _ = await provision_teacher(db, school=school, raw_password=PASSWORD)
            user.display_name = name.replace("_", " ").title()
            user.must_change_password = False
            if role:
                db.add(StaffRole(user_id=user.id, school_id=school.id, role=role))
            w.users[name] = user
        for cname in ("A", "B"):
            c = SchoolClass(school_id=school.id, name=f"10{cname}", grade=10)
            db.add(c)
            w.classes[cname] = c
        await db.flush()
        for lname, cname in (("a1", "A"), ("a2", "A"), ("b1", "B")):
            user, learner, _ = await provision_student(
                db, school=school, display_name=f"Learner {lname.upper()}", grade=10, raw_password=PASSWORD
            )
            user.must_change_password = False
            db.add(ClassMember(class_id=w.classes[cname].id, learner_id=learner.id))
            w.users[lname] = user
            w.learners[lname] = learner
        for tname, cname in (("teacher_a", "A"), ("teacher_b", "B")):
            db.add(TeachingAllocation(school_id=school.id, teacher_user_id=w.users[tname].id,
                                      subject_id=subject.id, class_id=w.classes[cname].id))
        parent = User(role="parent", school_id=school.id, student_number=f"G{tag[:5]}",
                      display_name="Parent A1", password_hash=hash_password(PASSWORD), must_change_password=False)
        db.add(parent)
        await db.flush()
        from app.models import ParentLink

        db.add(ParentLink(parent_user_id=parent.id, learner_id=w.learners["a1"].id,
                          relationship_to_learner="Mother", kind="guardian"))
        w.users["parent"] = parent
        await db.commit()
    return w
