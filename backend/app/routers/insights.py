"""
NEW 19 Nov 2026 (ADR-039, INSIGHTS): dashboards for circuit and district
officials (User role "official", see OfficialAssignment).

GET /insights/scope                -- my district(s)/circuit(s) and their schools
GET /insights/overview?circuit_id  -- every school in scope: participation,
                                      accuracy, band; weakest topics across them
GET /insights/schools/{id}         -- one school: grade x subject, weakest
                                      topics, classes

Aggregates only, over the last WINDOW_DAYS; groups with fewer than
MIN_LEARNERS learners are suppressed (app/services/insights.py).
"""

import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utcnow_naive
from app.core.database import get_db
from app.core.security import get_current_user
from app.models import (
    Attempt,
    Circuit,
    ClassMember,
    District,
    Learner,
    OfficialAssignment,
    Question,
    School,
    SchoolClass,
    Subject,
    Topic,
    User,
)
from app.services.insights import WINDOW_DAYS, GroupStats, present, weakest

router = APIRouter(prefix="/insights", tags=["insights"])

_CORRECT = func.sum(case((Attempt.is_correct.is_(True), 1), else_=0))


async def get_current_official(user: User = Depends(get_current_user)) -> User:
    if user.role != "official":
        raise HTTPException(status_code=403, detail="Education official access required")
    return user


async def _scope(db: AsyncSession, official: User) -> dict:
    """{"districts": [...], "circuits": [...], "school_ids": set} for this official."""
    assigns = (
        await db.execute(select(OfficialAssignment).where(OfficialAssignment.user_id == official.id))
    ).scalars().all()
    district_ids = {a.district_id for a in assigns if a.district_id}
    circuit_ids = {a.circuit_id for a in assigns if a.circuit_id}
    if district_ids:
        circuit_ids |= set(
            (await db.execute(select(Circuit.id).where(Circuit.district_id.in_(district_ids)))).scalars().all()
        )
    circuits = []
    if circuit_ids:
        circuits = (
            await db.execute(select(Circuit).where(Circuit.id.in_(circuit_ids)).order_by(Circuit.name))
        ).scalars().all()
    districts = []
    all_district_ids = district_ids | {c.district_id for c in circuits}
    if all_district_ids:
        districts = (
            await db.execute(select(District).where(District.id.in_(all_district_ids)).order_by(District.name))
        ).scalars().all()
    schools = []
    if circuit_ids:
        schools = (
            await db.execute(
                select(School)
                .where(School.circuit_id.in_(circuit_ids), School.kind == "school")
                .order_by(School.name)
            )
        ).scalars().all()
    return {
        "districts": districts,
        "circuits": circuits,
        "district_level": bool(district_ids),
        "schools": schools,
    }


def _answers_since():
    return utcnow_naive() - timedelta(days=WINDOW_DAYS)


@router.get("/scope")
async def my_scope(official: User = Depends(get_current_official), db: AsyncSession = Depends(get_db)) -> dict:
    s = await _scope(db, official)
    return {
        "display_name": official.display_name,
        "district_level": s["district_level"],
        "districts": [{"id": str(d.id), "name": d.name, "province": d.province} for d in s["districts"]],
        "circuits": [{"id": str(c.id), "name": c.name, "district_id": str(c.district_id)} for c in s["circuits"]],
        "school_count": len(s["schools"]),
        "window_days": WINDOW_DAYS,
    }


@router.get("/overview")
async def overview(
    circuit_id: uuid.UUID | None = Query(default=None),
    official: User = Depends(get_current_official),
    db: AsyncSession = Depends(get_db),
) -> dict:
    s = await _scope(db, official)
    schools = s["schools"]
    if circuit_id is not None:
        if circuit_id not in {c.id for c in s["circuits"]}:
            raise HTTPException(status_code=404, detail="Circuit not found")
        schools = [x for x in schools if x.circuit_id == circuit_id]
    ids = [x.id for x in schools]
    circuit_names = {c.id: c.name for c in s["circuits"]}
    if not ids:
        return {"schools": [], "weakest_topics": [], "totals": None, "window_days": WINDOW_DAYS}

    enrolled = dict(
        (
            await db.execute(
                select(User.school_id, func.count())
                .where(User.school_id.in_(ids), User.role == "student", User.is_active.is_(True))
                .group_by(User.school_id)
            )
        ).all()
    )
    since = _answers_since()
    per_school = {
        sid: (learners, answered, correct)
        for sid, learners, answered, correct in (
            await db.execute(
                select(
                    User.school_id,
                    func.count(func.distinct(Attempt.learner_id)),
                    func.count(Attempt.id),
                    _CORRECT,
                )
                .join(Learner, Attempt.learner_id == Learner.id)
                .join(User, Learner.user_id == User.id)
                .where(User.school_id.in_(ids), Attempt.is_correct.isnot(None), Attempt.created_at >= since)
                .group_by(User.school_id)
            )
        ).all()
    }
    school_rows = []
    for x in schools:
        learners, answered, correct = per_school.get(x.id, (0, 0, 0))
        row = present(
            GroupStats(str(x.id), x.name, learners, answered, int(correct or 0)),
            enrolled=enrolled.get(x.id, 0),
        )
        row["circuit"] = circuit_names.get(x.circuit_id)
        school_rows.append(row)

    topic_rows = (
        await db.execute(
            select(
                Topic.id,
                Topic.name,
                Subject.name,
                Subject.grade,
                func.count(func.distinct(Attempt.learner_id)),
                func.count(Attempt.id),
                _CORRECT,
                func.count(func.distinct(User.school_id)),
            )
            .join(Question, Attempt.question_id == Question.id)
            .join(Topic, Question.topic_id == Topic.id)
            .join(Subject, Topic.subject_id == Subject.id)
            .join(Learner, Attempt.learner_id == Learner.id)
            .join(User, Learner.user_id == User.id)
            .where(User.school_id.in_(ids), Attempt.is_correct.isnot(None), Attempt.created_at >= since)
            .group_by(Topic.id, Topic.name, Subject.name, Subject.grade)
        )
    ).all()
    topics = [
        GroupStats(
            str(tid),
            tname,
            learners,
            answered,
            int(correct or 0),
            {"subject": sname, "grade": grade, "schools": nschools},
        )
        for tid, tname, sname, grade, learners, answered, correct, nschools in topic_rows
    ]

    tot_learners = sum(v[0] for v in per_school.values())
    tot_answered = sum(v[1] for v in per_school.values())
    tot_correct = sum(int(v[2] or 0) for v in per_school.values())
    totals = present(
        GroupStats("all", "All schools", tot_learners, tot_answered, tot_correct),
        enrolled=sum(enrolled.values()),
    )
    return {
        "window_days": WINDOW_DAYS,
        "totals": totals,
        "schools": school_rows,
        "weakest_topics": weakest(topics),
    }


@router.get("/schools/{school_id}")
async def school_detail(
    school_id: uuid.UUID,
    official: User = Depends(get_current_official),
    db: AsyncSession = Depends(get_db),
) -> dict:
    s = await _scope(db, official)
    school = next((x for x in s["schools"] if x.id == school_id), None)
    if school is None:
        raise HTTPException(status_code=404, detail="School not found")
    since = _answers_since()
    base = (
        select()
        .select_from(Attempt)
        .join(Learner, Attempt.learner_id == Learner.id)
        .join(User, Learner.user_id == User.id)
        .join(Question, Attempt.question_id == Question.id)
        .join(Topic, Question.topic_id == Topic.id)
        .join(Subject, Topic.subject_id == Subject.id)
        .where(User.school_id == school.id, Attempt.is_correct.isnot(None), Attempt.created_at >= since)
    )
    stats_cols = (func.count(func.distinct(Attempt.learner_id)), func.count(Attempt.id), _CORRECT)

    grade_subject = (
        await db.execute(
            base.add_columns(Subject.grade, Subject.name, *stats_cols).group_by(Subject.grade, Subject.name)
        )
    ).all()
    by_subject = [
        present(GroupStats(f"{g}|{sname}", f"Grade {g} {sname}", l, a, int(c or 0), {"grade": g, "subject": sname}))
        for g, sname, l, a, c in sorted(grade_subject, key=lambda r: (r[0], r[1]))
    ]
    topic_rows = (
        await db.execute(
            base.add_columns(Topic.id, Topic.name, Subject.name, Subject.grade, *stats_cols).group_by(
                Topic.id, Topic.name, Subject.name, Subject.grade
            )
        )
    ).all()
    topics = [
        GroupStats(str(tid), tname, l, a, int(c or 0), {"subject": sname, "grade": g})
        for tid, tname, sname, g, l, a, c in topic_rows
    ]
    class_rows = (
        await db.execute(
            base.join(ClassMember, ClassMember.learner_id == Learner.id)
            .join(SchoolClass, ClassMember.class_id == SchoolClass.id)
            .add_columns(SchoolClass.id, SchoolClass.name, SchoolClass.grade, *stats_cols)
            .group_by(SchoolClass.id, SchoolClass.name, SchoolClass.grade)
        )
    ).all()
    classes = [
        present(GroupStats(str(cid), cname, l, a, int(c or 0), {"grade": g}))
        for cid, cname, g, l, a, c in sorted(class_rows, key=lambda r: (r[2], r[1]))
    ]
    return {
        "school": {"id": str(school.id), "name": school.name},
        "window_days": WINDOW_DAYS,
        "by_grade_subject": by_subject,
        "weakest_topics": weakest(topics, limit=10, min_answers=5),
        "classes": classes,
    }
