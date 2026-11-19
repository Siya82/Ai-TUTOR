"""
NEW 19 Nov 2026 (ADR-044): THUTOra ADMIN -- the school-management workspace.

Same platform, same users and records as TEACH; ADMIN is the interface for
the people who run the school (principal, deputy principal, school admin).
Most ADMIN screens reuse the existing /school/* and /admin/* endpoints;
this router adds what ADMIN needs on top:

  GET  /school/profile        -- any staff member (name, EMIS no., contacts, settings)
  PUT  /school/profile        -- school management only
  GET  /school/overview       -- school management only: the dashboard + to-dos
  POST /schools/registrations -- public "Register your school" request
"""

import time
import uuid
from collections import defaultdict, deque

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_staff_scope
from app.models import (
    ClassMember,
    ConsentRecord,
    Learner,
    LearnerGuardian,
    ParentLink,
    School,
    SchoolClass,
    SchoolRegistration,
    StaffRole,
    TeachingAllocation,
    User,
)
from app.services.family import normalize_sa_cellphone
from app.services.school_scope import StaffScope

router = APIRouter(tags=["admin-workspace"])

PROVINCES = [
    "Eastern Cape",
    "Free State",
    "Gauteng",
    "KwaZulu-Natal",
    "Limpopo",
    "Mpumalanga",
    "North West",
    "Northern Cape",
    "Western Cape",
]


def _require_manage(scope: StaffScope) -> None:
    if not scope.can_manage_school:
        raise HTTPException(
            status_code=403, detail="Only the principal, deputy principal or school admin can manage the school"
        )


class SchoolProfileIn(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    emis_number: str | None = Field(default=None, max_length=20)
    province: str | None = Field(default=None, max_length=40)
    quintile: int | None = Field(default=None, ge=1, le=5)
    phone: str | None = Field(default=None, max_length=30)
    email: str | None = Field(default=None, max_length=200)
    physical_address: str | None = Field(default=None, max_length=300)
    parent_signup_enabled: bool = True
    viewer_invites_enabled: bool = True


def _profile_out(s: School, scope: StaffScope) -> dict:
    return {
        "id": str(s.id),
        "name": s.name,
        "emis_number": s.emis_number,
        "province": s.province,
        "quintile": s.quintile,
        "phone": s.phone,
        "email": s.email,
        "physical_address": s.physical_address,
        "parent_signup_enabled": s.parent_signup_enabled,
        "viewer_invites_enabled": s.viewer_invites_enabled,
        "can_edit": scope.can_manage_school,
        "provinces": PROVINCES,
    }


def _blank(v: str | None) -> str | None:
    return (v or "").strip() or None


@router.get("/school/profile")
async def get_profile(scope: StaffScope = Depends(get_current_staff_scope), db: AsyncSession = Depends(get_db)) -> dict:
    return _profile_out(await db.get(School, scope.school_id), scope)


@router.put("/school/profile")
async def update_profile(
    payload: SchoolProfileIn, scope: StaffScope = Depends(get_current_staff_scope), db: AsyncSession = Depends(get_db)
) -> dict:
    _require_manage(scope)
    if payload.province and payload.province not in PROVINCES:
        raise HTTPException(status_code=400, detail="Choose a province from the list")
    emis = _blank(payload.emis_number)
    if emis and not emis.isdigit():
        raise HTTPException(status_code=400, detail="The EMIS number should be digits only")
    school = await db.get(School, scope.school_id)
    school.name = payload.name.strip()
    school.emis_number = emis
    school.province = payload.province or None
    school.quintile = payload.quintile
    school.phone = _blank(payload.phone)
    school.email = _blank(payload.email)
    school.physical_address = _blank(payload.physical_address)
    school.parent_signup_enabled = payload.parent_signup_enabled
    school.viewer_invites_enabled = payload.viewer_invites_enabled
    await db.commit()
    return _profile_out(school, scope)


def build_todos(o: dict) -> list[dict]:
    """Plain-language to-dos from the overview numbers (pure; unit tested)."""
    todos = []
    active = o["learners"]["active"]

    def add(n, one, many, tab):
        if n:
            todos.append({"text": (one if n == 1 else many).format(n=n), "tab": tab, "count": n})

    add(o["learners"]["not_in_class"], "{n} learner isn't in a class yet", "{n} learners aren't in a class yet", "classes")
    add(o["classes"]["without_teacher"], "{n} class has no teacher allocated", "{n} classes have no teacher allocated", "staff")
    add(o["staff"]["without_work"], "{n} staff member has no class or role yet", "{n} staff members have no class or role yet", "staff")
    add(active - o["learners"]["with_consent"], "{n} learner has no consent recorded", "{n} learners have no consent recorded", "learners")
    add(active - o["families"]["with_contact"], "{n} learner has no guardian cellphone on record", "{n} learners have no guardian cellphone on record", "learners")
    return todos


@router.get("/school/overview")
async def overview(scope: StaffScope = Depends(get_current_staff_scope), db: AsyncSession = Depends(get_db)) -> dict:
    _require_manage(scope)
    sid = scope.school_id
    active_learner = and_(User.school_id == sid, User.is_active.is_(True))

    by_grade = (
        await db.execute(
            select(Learner.grade, func.count())
            .join(User, Learner.user_id == User.id)
            .where(active_learner)
            .group_by(Learner.grade)
            .order_by(Learner.grade)
        )
    ).all()
    inactive = (
        await db.execute(
            select(func.count()).select_from(Learner).join(User, Learner.user_id == User.id)
            .where(User.school_id == sid, User.is_active.is_(False))
        )
    ).scalar_one()

    async def count_learners(extra_join, cond=None):
        q = (
            select(func.count(func.distinct(Learner.id)))
            .select_from(Learner)
            .join(User, Learner.user_id == User.id)
            .join(*extra_join)
            .where(active_learner)
        )
        if cond is not None:
            q = q.where(cond)
        return (await db.execute(q)).scalar_one()

    in_class = await count_learners((ClassMember, ClassMember.learner_id == Learner.id))
    with_consent = await count_learners(
        (ConsentRecord, ConsentRecord.learner_id == Learner.id), ConsentRecord.withdrawn_at.is_(None)
    )
    with_contact = await count_learners(
        (LearnerGuardian, LearnerGuardian.learner_id == Learner.id), LearnerGuardian.cellphone.is_not(None)
    )
    with_parent = await count_learners(
        (ParentLink, ParentLink.learner_id == Learner.id), ParentLink.kind == "guardian"
    )

    classes_total = (
        await db.execute(select(func.count()).select_from(SchoolClass).where(SchoolClass.school_id == sid))
    ).scalar_one()
    classes_taught = (
        await db.execute(
            select(func.count(func.distinct(TeachingAllocation.class_id))).where(
                TeachingAllocation.school_id == sid, TeachingAllocation.class_id.is_not(None)
            )
        )
    ).scalar_one()

    staff_ids = (
        await db.execute(
            select(User.id).where(User.school_id == sid, User.role == "teacher", User.is_active.is_(True))
        )
    ).scalars().all()
    busy = set(
        (await db.execute(select(TeachingAllocation.teacher_user_id).where(TeachingAllocation.school_id == sid)))
        .scalars()
        .all()
    ) | set((await db.execute(select(StaffRole.user_id).where(StaffRole.school_id == sid))).scalars().all())
    parents = (
        await db.execute(
            select(func.count()).select_from(User).where(
                User.school_id == sid, User.role == "parent", User.is_active.is_(True)
            )
        )
    ).scalar_one()

    active = sum(n for _, n in by_grade)
    out = {
        "learners": {
            "active": active,
            "inactive": inactive,
            "by_grade": [{"grade": g, "count": n} for g, n in by_grade],
            "not_in_class": active - in_class,
            "with_consent": with_consent,
        },
        "classes": {"total": classes_total, "without_teacher": max(classes_total - classes_taught, 0)},
        "staff": {"active": len(staff_ids), "without_work": len([u for u in staff_ids if u not in busy])},
        "families": {"with_contact": with_contact, "with_parent_login": with_parent, "parent_logins": parents},
    }
    out["todos"] = build_todos(out)
    return out


# --- public school registration ------------------------------------------------------

_reg_by_ip: dict[str, deque] = defaultdict(deque)


class RegistrationIn(BaseModel):
    school_name: str = Field(min_length=3, max_length=200)
    emis_number: str | None = Field(default=None, max_length=20)
    province: str = Field(max_length=40)
    contact_name: str = Field(min_length=2, max_length=100)
    contact_role: str = Field(min_length=2, max_length=50)
    contact_cellphone: str = Field(min_length=9, max_length=30)
    contact_email: str | None = Field(default=None, max_length=200)
    learner_estimate: int | None = Field(default=None, ge=1, le=10000)
    message: str | None = Field(default=None, max_length=2000)


@router.get("/schools/registrations/options")
async def registration_options() -> dict:
    return {"provinces": PROVINCES, "roles": ["Principal", "Deputy principal", "School admin", "SGB member", "Other"]}


@router.post("/schools/registrations", status_code=201)
async def register_school(payload: RegistrationIn, request: Request, db: AsyncSession = Depends(get_db)) -> dict:
    ip = request.client.host if request.client else "-"
    q = _reg_by_ip[ip]
    now = time.monotonic()
    while q and now - q[0] > 3600:
        q.popleft()
    if len(q) >= 5:
        raise HTTPException(status_code=429, detail="Too many requests. Please try again later.")
    if payload.province not in PROVINCES:
        raise HTTPException(status_code=400, detail="Choose a province from the list")
    try:
        cell = normalize_sa_cellphone(payload.contact_cellphone)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    emis = _blank(payload.emis_number)
    if emis and not emis.isdigit():
        raise HTTPException(status_code=400, detail="The EMIS number should be digits only")
    q.append(now)
    reg = SchoolRegistration(
        id=uuid.uuid4(),
        school_name=payload.school_name.strip(),
        emis_number=emis,
        province=payload.province,
        contact_name=payload.contact_name.strip(),
        contact_role=payload.contact_role.strip(),
        contact_cellphone=cell,
        contact_email=_blank(payload.contact_email),
        learner_estimate=payload.learner_estimate,
        message=_blank(payload.message),
    )
    db.add(reg)
    await db.commit()
    return {
        "reference": str(reg.id)[:8].upper(),
        "message": "Thank you. The THUTOra team will contact you to confirm your school and set up the principal's login.",
    }
