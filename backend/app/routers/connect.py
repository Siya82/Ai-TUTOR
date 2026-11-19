"""
NEW 19 Nov 2026 (ADR-038, CONNECT -- parents).

Parent side (role "parent"):
  GET  /parent/children                      -- the learners linked to me
  GET  /parent/children/{id}/overview        -- progress and work (no chats)
  GET  /parent/children/{id}/summary?lang=   -- a short summary, translated if asked
  GET  /parent/notices                       -- my school's notices for my children's grades
  POST /parent/notices/{id}/ack              -- "I've read this"

School side (staff):
  GET    /school/learners/{id}/parents               -- linked parents
  POST   /school/learners/{id}/parents               -- create a parent login (or link an existing one)
  DELETE /school/learners/{id}/parents/{user_id}     -- unlink
  GET    /school/notices                             -- notices with read/acknowledged counts
  POST   /school/notices                             -- post a notice (school management)
  DELETE /school/notices/{id}                        -- remove it (school management)
"""

import logging
import uuid
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utcnow_naive
from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_staff_scope, get_current_user
from app.models import (
    Assignment,
    AssignmentQuestion,
    AssignmentTarget,
    Attempt,
    Learner,
    NoticeAck,
    ParentLink,
    Question,
    School,
    SchoolNotice,
    Subject,
    Topic,
    User,
)
from app.services.assignments import get_learner_completions
from app.services.auth import _generate_unique_login_number, generate_temp_password, hash_password
from app.services.connect import (
    TOPIC_WINDOW_DAYS,
    TRANSLATE_SYSTEM_PROMPT,
    MarkedAnswer,
    WorkItem,
    child_overview,
    summary_text,
)
from app.services.personalization import HOME_LANGUAGES
from app.services.school_scope import StaffScope
from app.services.tutor import TutorClient

router = APIRouter(tags=["connect"])
log = logging.getLogger("thutora.connect")
_translator = TutorClient(model=settings.marking_model or None)
# (learner_id, language, day, text) -> translation. Small and per-process;
# a summary changes at most a few times a day, so this keeps translation
# cost to roughly one call per child, language and day.
_translations: dict[tuple, str] = {}


# --- parent side ---------------------------------------------------------------


async def get_current_parent(user: User = Depends(get_current_user)) -> User:
    if user.role != "parent":
        raise HTTPException(status_code=403, detail="Parent access required")
    return user


async def _my_child(db: AsyncSession, parent: User, learner_id: uuid.UUID) -> tuple[Learner, ParentLink]:
    row = (
        await db.execute(
            select(Learner, ParentLink)
            .join(ParentLink, ParentLink.learner_id == Learner.id)
            .join(User, Learner.user_id == User.id)
            .where(
                ParentLink.parent_user_id == parent.id,
                Learner.id == learner_id,
                User.is_active.is_(True),
            )
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Child not found")
    return row[0], row[1]


@router.get("/parent/children")
async def my_children(parent: User = Depends(get_current_parent), db: AsyncSession = Depends(get_db)) -> list[dict]:
    rows = (
        await db.execute(
            select(Learner, ParentLink.relationship_to_learner, ParentLink.kind)
            .join(ParentLink, ParentLink.learner_id == Learner.id)
            .join(User, Learner.user_id == User.id)
            .where(ParentLink.parent_user_id == parent.id, User.is_active.is_(True))
            .order_by(Learner.display_name)
        )
    ).all()
    return [
        {
            "learner_id": str(l.id),
            "display_name": l.display_name,
            "grade": l.grade,
            "relationship": rel,
            "kind": kind,  # ADR-043: "guardian" or "viewer"
        }
        for l, rel, kind in rows
    ]


async def _overview(db: AsyncSession, learner: Learner) -> dict:
    now = utcnow_naive()
    rows = (
        await db.execute(
            select(Topic.id, Topic.name, Subject.name, Attempt.is_correct, Attempt.created_at)
            .join(Question, Attempt.question_id == Question.id)
            .join(Topic, Question.topic_id == Topic.id)
            .join(Subject, Topic.subject_id == Subject.id)
            .where(
                Attempt.learner_id == learner.id,
                Attempt.is_correct.isnot(None),
                Attempt.created_at >= now - timedelta(days=TOPIC_WINDOW_DAYS),
            )
        )
    ).all()
    answers = [MarkedAnswer(tid, tname, sname, bool(ok), at) for tid, tname, sname, ok, at in rows]

    assignments = (
        await db.execute(
            select(Assignment)
            .join(AssignmentTarget, AssignmentTarget.assignment_id == Assignment.id)
            .where(AssignmentTarget.learner_id == learner.id)
            .order_by(Assignment.created_at.desc())
            .limit(20)
        )
    ).scalars().all()
    ids = [a.id for a in assignments]
    completions = await get_learner_completions(db, assignment_ids=ids, learner_id=learner.id)
    subjects: dict[uuid.UUID, set[str]] = {}
    if ids:
        for aid, sname in (
            await db.execute(
                select(AssignmentQuestion.assignment_id, Subject.name)
                .join(Question, AssignmentQuestion.question_id == Question.id)
                .join(Topic, Question.topic_id == Topic.id)
                .join(Subject, Topic.subject_id == Subject.id)
                .where(AssignmentQuestion.assignment_id.in_(ids))
            )
        ).all():
            subjects.setdefault(aid, set()).add(sname)
    work = []
    for a in assignments:
        c = completions.get(a.id)
        hidden = a.mode == "test" and not a.results_released
        work.append(
            WorkItem(
                title=a.title,
                subject_names=tuple(sorted(subjects.get(a.id, set()))),
                mode=a.mode,
                due_at=a.due_at,
                status=c.status if c else "not_started",
                marks_earned=None if hidden or c is None else c.marks_earned,
                marks_total=c.marks_total if c else 0,
            )
        )
    first_name = learner.display_name.split()[0] if learner.display_name else "Your child"
    return child_overview(first_name, answers, work, now)


@router.get("/parent/children/{learner_id}/overview")
async def child_progress(
    learner_id: uuid.UUID, parent: User = Depends(get_current_parent), db: AsyncSession = Depends(get_db)
) -> dict:
    learner, _ = await _my_child(db, parent, learner_id)
    data = await _overview(db, learner)
    data["grade"] = learner.grade
    return data


@router.get("/parent/children/{learner_id}/summary")
async def child_summary(
    learner_id: uuid.UUID,
    lang: str = Query("English", max_length=30),
    parent: User = Depends(get_current_parent),
    db: AsyncSession = Depends(get_db),
) -> dict:
    learner, _ = await _my_child(db, parent, learner_id)
    text = summary_text(await _overview(db, learner))
    if lang not in HOME_LANGUAGES or lang == "English":
        return {"language": "English", "text": text}
    key = (learner.id, lang, date.today(), text)
    if key not in _translations:
        try:
            _translations[key] = await _translator.ask(
                TRANSLATE_SYSTEM_PROMPT.format(language=lang),
                [{"role": "user", "content": text}],
                max_tokens=600,
            )
        except Exception as exc:  # noqa: BLE001 -- fall back to English, never fail the page
            log.warning("Summary translation failed: %s", exc)
            return {"language": "English", "text": text, "translation_failed": True}
    return {"language": lang, "text": _translations[key], "english": text}


async def _parent_grades(db: AsyncSession, parent: User) -> set[int]:
    return set(
        (
            await db.execute(
                select(Learner.grade)
                .join(ParentLink, ParentLink.learner_id == Learner.id)
                # ADR-043: notices go to parents/guardians, not invited viewers
                .where(ParentLink.parent_user_id == parent.id, ParentLink.kind == "guardian")
            )
        ).scalars().all()
    )


@router.get("/parent/notices")
async def parent_notices(parent: User = Depends(get_current_parent), db: AsyncSession = Depends(get_db)) -> list[dict]:
    grades = await _parent_grades(db, parent)
    if not grades:
        return []  # viewers only (ADR-043)
    notices = (
        await db.execute(
            select(SchoolNotice)
            .where(SchoolNotice.school_id == parent.school_id)
            .where(SchoolNotice.grade.is_(None) | SchoolNotice.grade.in_(grades or {-1}))
            .order_by(SchoolNotice.created_at.desc())
            .limit(50)
        )
    ).scalars().all()
    acked = set(
        (
            await db.execute(
                select(NoticeAck.notice_id).where(
                    NoticeAck.user_id == parent.id, NoticeAck.notice_id.in_([n.id for n in notices] or [None])
                )
            )
        ).scalars().all()
    )
    return [
        {
            "id": str(n.id),
            "title": n.title,
            "body": n.body,
            "grade": n.grade,
            "requires_ack": n.requires_ack,
            "acknowledged": n.id in acked,
            "created_at": n.created_at.isoformat() if n.created_at else None,
        }
        for n in notices
    ]


@router.post("/parent/notices/{notice_id}/ack", status_code=204)
async def ack_notice(
    notice_id: uuid.UUID, parent: User = Depends(get_current_parent), db: AsyncSession = Depends(get_db)
) -> None:
    notice = await db.get(SchoolNotice, notice_id)
    grades = await _parent_grades(db, parent)
    if notice is None or notice.school_id != parent.school_id or (notice.grade is not None and notice.grade not in grades):
        raise HTTPException(status_code=404, detail="Notice not found")
    exists = (
        await db.execute(select(NoticeAck.id).where(NoticeAck.notice_id == notice.id, NoticeAck.user_id == parent.id))
    ).scalar_one_or_none()
    if exists is None:
        db.add(NoticeAck(notice_id=notice.id, user_id=parent.id))
        await db.commit()


# --- school side ---------------------------------------------------------------


class ParentCreate(BaseModel):
    display_name: str = Field(default="", max_length=100)
    relationship_to_learner: str = Field(default="Parent", min_length=1, max_length=50)
    # Link a parent who already has a login (e.g. a sibling's parent) instead of creating one.
    existing_login_number: str | None = Field(default=None, max_length=50)


class NoticeCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=4000)
    grade: int | None = Field(default=None, ge=1, le=12)
    requires_ack: bool = False


async def _school_learner(db: AsyncSession, learner_id: uuid.UUID, scope: StaffScope) -> Learner:
    learner = (
        await db.execute(
            select(Learner)
            .join(User, Learner.user_id == User.id)
            .where(Learner.id == learner_id, User.school_id == scope.school_id)
        )
    ).scalar_one_or_none()
    if learner is None or not (scope.can_manage_school or scope.can_see_roster(learner.id)):
        raise HTTPException(status_code=404, detail="Learner not found")
    return learner


@router.get("/school/learners/{learner_id}/parents")
async def list_parents(
    learner_id: uuid.UUID,
    scope: StaffScope = Depends(get_current_staff_scope),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    learner = await _school_learner(db, learner_id, scope)
    rows = (
        await db.execute(
            select(User, ParentLink.relationship_to_learner, ParentLink.kind)
            .join(ParentLink, ParentLink.parent_user_id == User.id)
            .where(ParentLink.learner_id == learner.id)
        )
    ).all()
    return [
        {
            "user_id": str(u.id),
            "display_name": u.display_name,
            "login_number": u.student_number,
            "relationship": rel,
            "kind": kind,  # ADR-043
            "is_active": bool(u.is_active),
        }
        for u, rel, kind in rows
    ]


@router.post("/school/learners/{learner_id}/parents")
async def add_parent(
    learner_id: uuid.UUID,
    payload: ParentCreate,
    scope: StaffScope = Depends(get_current_staff_scope),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Creates a parent login (one-time password shown once) and links it,
    or links an existing parent login from this school."""
    learner = await _school_learner(db, learner_id, scope)
    temp_password = None
    if payload.existing_login_number:
        parent = (
            await db.execute(
                select(User).where(
                    User.school_id == scope.school_id,
                    User.role == "parent",
                    User.student_number == payload.existing_login_number.strip(),
                )
            )
        ).scalar_one_or_none()
        if parent is None:
            raise HTTPException(status_code=404, detail="No parent login with that number at this school")
    else:
        if not payload.display_name.strip():
            raise HTTPException(status_code=400, detail="Enter the parent's name")
        school = await db.get(School, scope.school_id)
        temp_password = generate_temp_password()
        parent = User(
            role="parent",
            school_id=school.id,
            student_number=await _generate_unique_login_number(db, school),
            display_name=payload.display_name.strip(),
            password_hash=hash_password(temp_password),
            must_change_password=True,
        )
        db.add(parent)
        await db.flush()
    existing = (
        await db.execute(
            select(ParentLink).where(ParentLink.parent_user_id == parent.id, ParentLink.learner_id == learner.id)
        )
    ).scalar_one_or_none()
    if existing is None:
        db.add(
            ParentLink(
                parent_user_id=parent.id,
                learner_id=learner.id,
                relationship_to_learner=payload.relationship_to_learner.strip(),
                created_by_user_id=scope.user_id,
            )
        )
    await db.commit()
    return {
        "user_id": str(parent.id),
        "display_name": parent.display_name,
        "login_number": parent.student_number,
        "temp_password": temp_password,
    }


@router.delete("/school/learners/{learner_id}/parents/{parent_user_id}", status_code=204)
async def remove_parent(
    learner_id: uuid.UUID,
    parent_user_id: uuid.UUID,
    scope: StaffScope = Depends(get_current_staff_scope),
    db: AsyncSession = Depends(get_db),
) -> None:
    learner = await _school_learner(db, learner_id, scope)
    await db.execute(
        delete(ParentLink).where(ParentLink.learner_id == learner.id, ParentLink.parent_user_id == parent_user_id)
    )
    await db.commit()


@router.get("/school/notices")
async def school_notices(
    scope: StaffScope = Depends(get_current_staff_scope), db: AsyncSession = Depends(get_db)
) -> list[dict]:
    notices = (
        await db.execute(
            select(SchoolNotice)
            .where(SchoolNotice.school_id == scope.school_id)
            .order_by(SchoolNotice.created_at.desc())
            .limit(50)
        )
    ).scalars().all()
    ack_counts = dict(
        (
            await db.execute(
                select(NoticeAck.notice_id, func.count())
                .where(NoticeAck.notice_id.in_([n.id for n in notices] or [None]))
                .group_by(NoticeAck.notice_id)
            )
        ).all()
    )
    # Parents each notice reaches: linked to an active learner in that grade (or any grade).
    rows = (
        await db.execute(
            select(ParentLink.parent_user_id, Learner.grade)
            .join(Learner, ParentLink.learner_id == Learner.id)
            .join(User, ParentLink.parent_user_id == User.id)
            .where(User.school_id == scope.school_id, User.is_active.is_(True), ParentLink.kind == "guardian")
        )
    ).all()
    parents_all = {p for p, _ in rows}
    parents_by_grade: dict[int, set] = {}
    for p, g in rows:
        parents_by_grade.setdefault(g, set()).add(p)
    return [
        {
            "id": str(n.id),
            "title": n.title,
            "body": n.body,
            "grade": n.grade,
            "requires_ack": n.requires_ack,
            "created_at": n.created_at.isoformat() if n.created_at else None,
            "acknowledged": ack_counts.get(n.id, 0),
            "audience": len(parents_all if n.grade is None else parents_by_grade.get(n.grade, set())),
        }
        for n in notices
    ]


@router.post("/school/notices")
async def post_notice(
    payload: NoticeCreate,
    scope: StaffScope = Depends(get_current_staff_scope),
    db: AsyncSession = Depends(get_db),
) -> dict:
    if not scope.can_manage_school:
        raise HTTPException(status_code=403, detail="Only school management can post notices")
    notice = SchoolNotice(
        school_id=scope.school_id,
        title=payload.title.strip(),
        body=payload.body.strip(),
        grade=payload.grade,
        requires_ack=payload.requires_ack,
        created_by_user_id=scope.user_id,
    )
    db.add(notice)
    await db.commit()
    return {"id": str(notice.id)}


@router.delete("/school/notices/{notice_id}", status_code=204)
async def delete_notice(
    notice_id: uuid.UUID,
    scope: StaffScope = Depends(get_current_staff_scope),
    db: AsyncSession = Depends(get_db),
) -> None:
    if not scope.can_manage_school:
        raise HTTPException(status_code=403, detail="Only school management can remove notices")
    notice = await db.get(SchoolNotice, notice_id)
    if notice is None or notice.school_id != scope.school_id:
        raise HTTPException(status_code=404, detail="Notice not found")
    await db.execute(delete(NoticeAck).where(NoticeAck.notice_id == notice.id))
    await db.delete(notice)
    await db.commit()
