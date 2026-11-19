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

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.audit import record as audit  # code review 19 Nov #11
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
from app.services import rate_limit
from app.services.family import normalize_sa_cellphone
from app.services.school_scope import StaffScope

router = APIRouter(tags=["admin-workspace"])
log = logging.getLogger("thutora.registrations")

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
    require_consent: bool = False  # deep scan M1
    ai_budget_usd_month: float | None = Field(default=None, ge=0, le=100000)  # deep scan H5


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
        "require_consent": s.require_consent,
        "ai_budget_usd_month": float(s.ai_budget_usd_month) if s.ai_budget_usd_month is not None else None,
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
    school.require_consent = payload.require_consent
    school.ai_budget_usd_month = payload.ai_budget_usd_month
    await audit(db, scope.user_id, scope.school_id, "school.settings", "school", school.id, {"parent_signup_enabled": school.parent_signup_enabled, "viewer_invites_enabled": school.viewer_invites_enabled, "require_consent": school.require_consent, "ai_budget_usd_month": payload.ai_budget_usd_month})
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
    if await rate_limit.too_many(db, f"register:ip:{ip}", 5, 3600):  # deep scan L6: in the database
        raise HTTPException(status_code=429, detail="Too many requests. Please try again later.")
    await rate_limit.hit(db, f"register:ip:{ip}")
    if payload.province not in PROVINCES:
        raise HTTPException(status_code=400, detail="Choose a province from the list")
    try:
        cell = normalize_sa_cellphone(payload.contact_cellphone)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    emis = _blank(payload.emis_number)
    if emis and not emis.isdigit():
        raise HTTPException(status_code=400, detail="The EMIS number should be digits only")
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
    # code review 19 Nov #16: make a new request impossible to miss in the logs
    log.warning(
        "NEW SCHOOL REGISTRATION %s: %s (%s), contact %s. Review with: python -m scripts.manage_registrations show %s",
        str(reg.id)[:8].upper(), reg.school_name, reg.province, reg.contact_name, str(reg.id)[:8].upper(),
    )
    return {
        "reference": str(reg.id)[:8].upper(),
        "message": "Thank you. The THUTOra team will contact you to confirm your school and set up the principal's login.",
    }


# --- audit trail (code review 19 Nov #11) ------------------------------------------------


@router.get("/school/audit")
async def school_audit(
    limit: int = 100,
    scope: StaffScope = Depends(get_current_staff_scope),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """The last sensitive actions at this school, newest first -- principal,
    deputy and school admin only. Names are resolved now (a deleted learner
    shows as "a deleted learner")."""
    _require_manage(scope)
    from app.models import AuditEvent
    from app.services.audit import LABELS

    events = (
        await db.execute(
            select(AuditEvent)
            .where(AuditEvent.school_id == scope.school_id)
            .order_by(AuditEvent.created_at.desc())
            .limit(max(1, min(limit, 500)))
        )
    ).scalars().all()
    user_ids = {e.actor_user_id for e in events if e.actor_user_id}
    learner_ids, target_user_ids = set(), set()
    for e in events:
        try:
            tid = uuid.UUID(e.target_id) if e.target_id else None
        except ValueError:
            tid = None
        if tid and e.target_type == "learner":
            learner_ids.add(tid)
        elif tid and e.target_type == "user":
            target_user_ids.add(tid)
    names = {}
    if user_ids | target_user_ids:
        for uid, dn, num in (
            await db.execute(
                select(User.id, User.display_name, User.student_number).where(User.id.in_(user_ids | target_user_ids))
            )
        ).all():
            names[str(uid)] = dn or num
    if learner_ids:
        for lid, dn in (await db.execute(select(Learner.id, Learner.display_name).where(Learner.id.in_(learner_ids)))).all():
            names[str(lid)] = dn
    out = []
    for e in events:
        target = None
        if e.target_type in ("learner", "user"):
            target = names.get(e.target_id) or f"a deleted {e.target_type}"
        elif e.target_type == "grade":
            target = f"Grade {e.target_id}"
        out.append(
            {
                "at": e.created_at.isoformat(),
                "action": e.action,
                "label": LABELS.get(e.action, e.action),
                "by": names.get(str(e.actor_user_id), "THUTOra") if e.actor_user_id else "THUTOra",
                "target": target,
                "details": e.details or {},
            }
        )
    return {"events": out}



@router.get("/school/ai-usage")
async def school_ai_usage(scope: StaffScope = Depends(get_current_staff_scope), db: AsyncSession = Depends(get_db)) -> dict:
    """deep scan H5: this month's AI use and cost for the school, and its budget."""
    _require_manage(scope)
    from app.services.ai_cost import school_month

    data = await school_month(db, scope.school_id)
    school = await db.get(School, scope.school_id)
    data["budget_usd"] = float(school.ai_budget_usd_month) if school.ai_budget_usd_month is not None else None
    return data
