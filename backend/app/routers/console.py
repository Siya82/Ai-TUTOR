"""
NEW 23 Nov 2026 (ADR-051). THUTOra Console -- Zynora's internal tool.

Everything under /console is for Zynora staff only (ConsoleStaff), never for
school logins. The router-level guard:
- 404s every route when CONSOLE_ENABLED=false;
- in production, refuses calls that don't come from CONSOLE_ORIGINS, and
  anywhere refuses calls from a school app's address.

Roles: agent (tickets, read-only school lookup) < lead (registrations, schools,
principals, officials, the audit log) < director (Console staff).

Every action is audited with the staff member's id. Actions on a school also
appear in that school's ADMIN -> Activity, as "THUTOra support".

What the Console never shows: learner names, marks, work or tutor
conversations. There are no endpoints for them here, and tests check that.
"""

import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utcnow_naive
from app.core.config import settings
from app.core.database import get_db
from app.models import (
    AuditEvent,
    Circuit,
    ConsoleStaff,
    District,
    OfficialAssignment,
    School,
    SchoolClass,
    SchoolRegistration,
    StaffRole,
    SupportMessage,
    SupportTicket,
    User,
)
from app.services import onboarding, rate_limit, totp
from app.services.auth import generate_temp_password, hash_password, verify_password
from app.services.console_auth import ROLE_LABEL, ROLES, at_least, create_console_token, decode_console_token
from app.services.school_scope import ROLE_LABELS, SCHOOL_ROLES
from app.services.support import CATEGORIES, PRIORITY_LABEL

IS_PRODUCTION = settings.environment.lower() in ("production", "prod")


async def console_guard(request: Request) -> None:
    if not settings.console_enabled:
        raise HTTPException(status_code=404, detail="Not Found")
    origin = request.headers.get("origin")
    if origin and origin in settings.cors_origins and origin not in settings.console_origins:
        raise HTTPException(status_code=403, detail="The Console can't be used from a school app.")
    if IS_PRODUCTION and origin not in settings.console_origins:
        raise HTTPException(status_code=403, detail="Use the THUTOra Console website.")


router = APIRouter(prefix="/console", tags=["console"], dependencies=[Depends(console_guard)])

# --------------------------------------------------------------------------- auth


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "-"


async def _staff_from_token(authorization: str | None, db: AsyncSession, stage: str) -> ConsoleStaff:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not signed in")
    payload = decode_console_token(authorization.removeprefix("Bearer ").strip())
    if payload is None or payload.get("stage") != stage:
        raise HTTPException(status_code=401, detail="Session ended. Please sign in again.")
    try:
        staff = await db.get(ConsoleStaff, uuid.UUID(str(payload.get("sub"))))
    except ValueError:
        staff = None
    if staff is None or not staff.is_active or int(payload.get("ver", -1)) != staff.token_version:
        raise HTTPException(status_code=401, detail="Session ended. Please sign in again.")
    return staff


async def current_staff_any(
    authorization: str | None = Header(default=None), db: AsyncSession = Depends(get_db)
) -> ConsoleStaff:
    """Signed in with both steps; a temporary password is still allowed (for /me and change-password)."""
    return await _staff_from_token(authorization, db, "full")


def require(minimum: str):
    async def dep(staff: ConsoleStaff = Depends(current_staff_any)) -> ConsoleStaff:
        if staff.must_change_password:
            raise HTTPException(status_code=403, detail="Please change your temporary password first.")
        if not at_least(staff.role, minimum):
            raise HTTPException(status_code=403, detail=f"This needs a {ROLE_LABEL[minimum].lower()} or above.")
        return staff

    return dep


async def _audit(db, staff: ConsoleStaff, action: str, school_id=None, target_type=None, target_id=None, details=None):
    db.add(
        AuditEvent(
            console_staff_id=staff.id,
            school_id=school_id,
            action=action,
            target_type=target_type,
            target_id=str(target_id) if target_id is not None else None,
            details=details,
        )
    )


def _me(staff: ConsoleStaff) -> dict:
    return {
        "id": str(staff.id),
        "email": staff.email,
        "display_name": staff.display_name,
        "role": staff.role,
        "role_label": ROLE_LABEL[staff.role],
        "must_change_password": staff.must_change_password,
    }


class LoginIn(BaseModel):
    email: str = Field(min_length=3, max_length=200)
    password: str = Field(min_length=1, max_length=200)


LOGIN_MAX, IP_MAX, CODE_MAX, WINDOW = 5, 50, 5, 15 * 60


@router.post("/auth/login")
async def login(body: LoginIn, request: Request, db: AsyncSession = Depends(get_db)) -> dict:
    """Step 1: email and password. Returns a 5-minute token for step 2, and --
    the first time -- the authenticator set-up details."""
    email = body.email.strip().lower()
    ip = _client_ip(request)
    if await rate_limit.too_many(db, f"console:login:{email}", LOGIN_MAX, WINDOW) or await rate_limit.too_many(
        db, f"console:ip:{ip}", IP_MAX, WINDOW
    ):
        raise HTTPException(status_code=429, detail="Too many attempts. Wait 15 minutes and try again.")
    staff = (await db.execute(select(ConsoleStaff).where(ConsoleStaff.email == email))).scalar_one_or_none()
    if staff is None or not staff.is_active or not verify_password(body.password, staff.password_hash):
        await rate_limit.hit(db, f"console:login:{email}")
        await rate_limit.hit(db, f"console:ip:{ip}")
        await db.commit()
        raise HTTPException(status_code=401, detail="Wrong email or password.")
    out = {"token": create_console_token(str(staff.id), staff.role, staff.token_version, stage="mfa")}
    if staff.totp_confirmed and staff.totp_secret:
        out["step"] = "code"
    else:
        staff.totp_secret = totp.new_secret()  # a fresh secret until one is confirmed
        out.update(step="setup", secret=staff.totp_secret, otpauth_uri=totp.otpauth_uri(staff.totp_secret, staff.email))
    await db.commit()
    return out


class CodeIn(BaseModel):
    code: str = Field(min_length=6, max_length=8)


@router.post("/auth/verify")
async def verify(body: CodeIn, authorization: str | None = Header(default=None), db: AsyncSession = Depends(get_db)) -> dict:
    """Step 2: the 6-digit code from the authenticator app."""
    staff = await _staff_from_token(authorization, db, "mfa")
    key = f"console:code:{staff.id}"
    if await rate_limit.too_many(db, key, CODE_MAX, WINDOW):
        raise HTTPException(status_code=429, detail="Too many wrong codes. Wait 15 minutes and try again.")
    step = totp.match_step(staff.totp_secret or "", body.code)
    if step is None or (staff.totp_last_step is not None and step <= staff.totp_last_step):
        await rate_limit.hit(db, key)
        await db.commit()
        raise HTTPException(status_code=401, detail="That code didn't work. Use the newest code in the app.")
    first_time = not staff.totp_confirmed
    staff.totp_confirmed = True
    staff.totp_last_step = step
    staff.last_login_at = utcnow_naive()
    await _audit(db, staff, "console.2fa_setup" if first_time else "console.login")
    await db.commit()
    return {
        "token": create_console_token(str(staff.id), staff.role, staff.token_version),
        "expires_in_minutes": settings.console_session_minutes,
        "me": _me(staff),
    }


@router.get("/me")
async def me(staff: ConsoleStaff = Depends(current_staff_any)) -> dict:
    return _me(staff)


class PasswordIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=12, max_length=72)


@router.post("/auth/change-password")
async def change_password(
    body: PasswordIn, staff: ConsoleStaff = Depends(current_staff_any), db: AsyncSession = Depends(get_db)
) -> dict:
    if not verify_password(body.current_password, staff.password_hash):
        raise HTTPException(status_code=400, detail="Your current password is wrong.")
    if body.new_password == body.current_password:
        raise HTTPException(status_code=400, detail="Choose a different password.")
    staff.password_hash = hash_password(body.new_password)
    staff.must_change_password = False
    staff.token_version += 1
    await _audit(db, staff, "console.password")
    await db.commit()
    return {"token": create_console_token(str(staff.id), staff.role, staff.token_version), "me": _me(staff)}


@router.post("/auth/logout", status_code=204)
async def logout(staff: ConsoleStaff = Depends(current_staff_any), db: AsyncSession = Depends(get_db)) -> None:
    staff.token_version += 1  # ends this session (and any other) at once
    await db.commit()


# --------------------------------------------------------------------------- tickets (agent)

ORDER = case({"p1": 1, "p2": 2, "p3": 3, "p4": 4}, value=SupportTicket.priority, else_=5)
TICKET_VIEWS = {
    "open": [SupportTicket.status == "open"],
    "waiting_on_school": [SupportTicket.status == "waiting_on_school"],
    "resolved": [SupportTicket.status == "resolved"],
    "unresolved": [SupportTicket.status != "resolved"],
}


def _ticket_row(t: SupportTicket, school_name: str | None) -> dict:
    return {
        "number": t.number,
        "subject": t.subject,
        "priority": t.priority,
        "priority_label": PRIORITY_LABEL.get(t.priority, t.priority),
        "status": t.status,
        "category": CATEGORIES.get(t.category, (t.category,))[0],
        "product": t.product,
        "school_id": str(t.school_id),
        "school": school_name,
        "created_at": t.created_at.isoformat(),
        "updated_at": t.updated_at.isoformat(),
    }


@router.get("/tickets")
async def list_tickets(
    view: str = "open", staff: ConsoleStaff = Depends(require("agent")), db: AsyncSession = Depends(get_db)
) -> dict:
    if view not in TICKET_VIEWS:
        raise HTTPException(status_code=400, detail="Unknown view")
    q = select(SupportTicket, School.name).join(School, School.id == SupportTicket.school_id).where(*TICKET_VIEWS[view])
    order = [SupportTicket.updated_at.desc()] if view == "resolved" else [ORDER, SupportTicket.created_at]
    rows = (await db.execute(q.order_by(*order).limit(300))).all()
    counts = dict(
        (await db.execute(select(SupportTicket.status, func.count()).group_by(SupportTicket.status))).all()
    )
    return {"tickets": [_ticket_row(t, name) for t, name in rows], "counts": counts}


async def _ticket(db, number: int) -> SupportTicket:
    t = (await db.execute(select(SupportTicket).where(SupportTicket.number == number))).scalar_one_or_none()
    if t is None:
        raise HTTPException(status_code=404, detail=f"No ticket {number}.")
    return t


async def _ticket_detail(db, t: SupportTicket) -> dict:
    school = await db.get(School, t.school_id)
    creator = await db.get(User, t.created_by_user_id)
    msgs = (
        await db.execute(select(SupportMessage).where(SupportMessage.ticket_id == t.id).order_by(SupportMessage.created_at))
    ).scalars().all()
    staff_names = {
        s.id: s.display_name
        for s in (
            await db.execute(select(ConsoleStaff).where(ConsoleStaff.id.in_({m.console_staff_id for m in msgs if m.console_staff_id})))
        ).scalars()
    } if any(m.console_staff_id for m in msgs) else {}
    user_names = {}
    uids = {m.author_user_id for m in msgs if m.author_user_id}
    if uids:
        user_names = {u: (d or n) for u, d, n in (await db.execute(select(User.id, User.display_name, User.student_number).where(User.id.in_(uids)))).all()}
    return {
        **_ticket_row(t, school.name if school else None),
        "context": t.context or {},
        "from": {
            "name": (creator.display_name or creator.student_number) if creator else None,
            "login": creator.student_number if creator else None,
            "role": creator.role if creator else None,
        },
        "messages": [
            {
                "at": m.created_at.isoformat(),
                "from_zynora": m.from_zynora,
                "author": (staff_names.get(m.console_staff_id) or "THUTOra support")
                if m.from_zynora
                else user_names.get(m.author_user_id, "School"),
                "body": m.body,
            }
            for m in msgs
        ],
    }


@router.get("/tickets/{number}")
async def get_ticket(number: int, staff: ConsoleStaff = Depends(require("agent")), db: AsyncSession = Depends(get_db)) -> dict:
    return await _ticket_detail(db, await _ticket(db, number))


class ReplyIn(BaseModel):
    body: str = Field(min_length=1, max_length=5000)
    resolve: bool = False


@router.post("/tickets/{number}/reply")
async def reply_ticket(
    number: int, body: ReplyIn, staff: ConsoleStaff = Depends(require("agent")), db: AsyncSession = Depends(get_db)
) -> dict:
    t = await _ticket(db, number)
    now = utcnow_naive()
    db.add(SupportMessage(ticket_id=t.id, from_zynora=True, console_staff_id=staff.id, body=body.body.strip(), created_at=now))
    t.status = "resolved" if body.resolve else "waiting_on_school"
    t.updated_at = now
    t.resolved_at = now if body.resolve else None
    await _audit(db, staff, "ticket.resolve" if body.resolve else "ticket.reply", t.school_id, "ticket", t.number)
    await db.commit()
    return await _ticket_detail(db, t)


class StatusIn(BaseModel):
    priority: str | None = None
    status: str | None = None


@router.post("/tickets/{number}/update")
async def update_ticket(
    number: int, body: StatusIn, staff: ConsoleStaff = Depends(require("agent")), db: AsyncSession = Depends(get_db)
) -> dict:
    """Change priority, or reopen / resolve without a message."""
    t = await _ticket(db, number)
    if body.priority:
        if body.priority not in PRIORITY_LABEL:
            raise HTTPException(status_code=400, detail="Unknown priority")
        await _audit(db, staff, "ticket.priority", t.school_id, "ticket", t.number, {"from": t.priority, "to": body.priority})
        t.priority = body.priority
    if body.status:
        if body.status not in ("open", "waiting_on_school", "resolved"):
            raise HTTPException(status_code=400, detail="Unknown status")
        await _audit(db, staff, "ticket.status", t.school_id, "ticket", t.number, {"from": t.status, "to": body.status})
        t.status = body.status
        t.resolved_at = utcnow_naive() if body.status == "resolved" else None
    t.updated_at = utcnow_naive()
    await db.commit()
    return await _ticket_detail(db, t)


# --------------------------------------------------------------------------- schools (agent reads, lead acts)


async def _counts(db, school_ids: list[uuid.UUID]) -> dict:
    if not school_ids:
        return {}
    learners = dict(
        (
            await db.execute(
                select(User.school_id, func.count())
                .where(User.school_id.in_(school_ids), User.role == "student", User.is_active.is_(True))
                .group_by(User.school_id)
            )
        ).all()
    )
    staff = dict(
        (
            await db.execute(
                select(User.school_id, func.count())
                .where(User.school_id.in_(school_ids), User.role == "teacher", User.is_active.is_(True))
                .group_by(User.school_id)
            )
        ).all()
    )
    principals = dict(
        (
            await db.execute(
                select(StaffRole.school_id, func.count())
                .join(User, User.id == StaffRole.user_id)
                .where(StaffRole.school_id.in_(school_ids), StaffRole.role == "principal", User.is_active.is_(True))
                .group_by(StaffRole.school_id)
            )
        ).all()
    )
    return {sid: (learners.get(sid, 0), staff.get(sid, 0), principals.get(sid, 0)) for sid in school_ids}


def _school_row(s: School, counts: tuple, circuit: str | None) -> dict:
    learners, staff, principals = counts
    return {
        "id": str(s.id),
        "name": s.name,
        "kind": s.kind,
        "emis_number": s.emis_number,
        "province": s.province,
        "circuit": circuit,
        "learners": learners,
        "staff": staff,
        "has_principal": principals > 0,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


@router.get("/schools")
async def list_schools(
    q: str = "", staff: ConsoleStaff = Depends(require("agent")), db: AsyncSession = Depends(get_db)
) -> dict:
    stmt = select(School, Circuit.name).outerjoin(Circuit, Circuit.id == School.circuit_id).where(School.kind == "school")
    if q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where((School.name.ilike(like)) | (School.emis_number.ilike(like)))
    rows = (await db.execute(stmt.order_by(School.name).limit(200))).all()
    counts = await _counts(db, [s.id for s, _ in rows])
    return {"schools": [_school_row(s, counts[s.id], c) for s, c in rows]}


async def _school(db, school_id: uuid.UUID) -> School:
    s = await db.get(School, school_id)
    if s is None or s.kind != "school":
        raise HTTPException(status_code=404, detail="No such school.")
    return s


@router.get("/schools/{school_id}")
async def get_school(
    school_id: uuid.UUID, staff: ConsoleStaff = Depends(require("agent")), db: AsyncSession = Depends(get_db)
) -> dict:
    """The school's profile, counts and management team. Staff names only --
    never learner names, marks or work."""
    s = await _school(db, school_id)
    circuit = await db.get(Circuit, s.circuit_id) if s.circuit_id else None
    counts = (await _counts(db, [s.id]))[s.id]
    classes = (await db.execute(select(func.count()).select_from(SchoolClass).where(SchoolClass.school_id == s.id))).scalar_one()
    roles = (
        await db.execute(
            select(StaffRole, User)
            .join(User, User.id == StaffRole.user_id)
            .where(StaffRole.school_id == s.id, StaffRole.role.in_(SCHOOL_ROLES))
            .order_by(StaffRole.role, User.display_name)
        )
    ).all()
    team = [
        {
            "role_id": str(r.id),
            "role": r.role,
            "role_label": ROLE_LABELS.get(r.role, r.role),
            "subject": r.subject_name,
            "user_id": str(u.id),
            "name": u.display_name or u.student_number,
            "login": u.student_number,
            "active": u.is_active,
        }
        for r, u in roles
    ]
    staff_list = [
        {"user_id": str(u.id), "name": u.display_name or u.student_number, "login": u.student_number}
        for u in (
            await db.execute(
                select(User).where(User.school_id == s.id, User.role == "teacher", User.is_active.is_(True)).order_by(User.display_name)
            )
        ).scalars()
    ]
    tickets = (
        await db.execute(select(SupportTicket).where(SupportTicket.school_id == s.id).order_by(SupportTicket.created_at.desc()).limit(10))
    ).scalars().all()
    return {
        **_school_row(s, counts, circuit.name if circuit else None),
        "classes": classes,
        "phone": s.phone,
        "email": s.email,
        "quintile": s.quintile,
        "team": team,
        "staff_list": staff_list,
        "tickets": [_ticket_row(t, s.name) for t in tickets],
    }


class NewSchoolIn(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    emis_number: str | None = Field(default=None, max_length=20)
    province: str | None = Field(default=None, max_length=40)
    email: str | None = Field(default=None, max_length=200)
    principal_name: str = Field(min_length=2, max_length=100)
    first_role: str = "principal"
    staff_number: str | None = Field(default=None, max_length=50)


def _credentials(user: User, temp: str, school: School) -> dict:
    return {
        "name": user.display_name,
        "school": school.name,
        "login": user.student_number,
        "temp_password": temp,  # shown once, never stored in plain text
    }


@router.post("/schools", status_code=201)
async def create_school(
    body: NewSchoolIn, staff: ConsoleStaff = Depends(require("lead")), db: AsyncSession = Depends(get_db)
) -> dict:
    """Set up a school directly (e.g. a pilot school under a signed agreement)."""
    try:
        school = await onboarding.create_school(db, name=body.name, emis_number=body.emis_number, province=body.province, email=body.email)
        user, temp = await onboarding.add_first_login(db, school, body.principal_name, body.first_role, body.staff_number)
    except onboarding.OnboardingError as e:
        raise onboarding.http_error(e)
    await _audit(db, staff, "school.create", school.id, "school", school.id, {"name": school.name})
    await _audit(db, staff, "principal.add" if body.first_role == "principal" else "staff.create", school.id, "user", user.id,
                 {"role": body.first_role})
    await db.commit()
    return {"school_id": str(school.id), "credentials": _credentials(user, temp, school)}


class PrincipalIn(BaseModel):
    display_name: str | None = Field(default=None, max_length=100)
    staff_number: str | None = Field(default=None, max_length=50)
    existing_user_id: uuid.UUID | None = None


@router.post("/schools/{school_id}/principal")
async def add_principal(
    school_id: uuid.UUID, body: PrincipalIn, staff: ConsoleStaff = Depends(require("lead")), db: AsyncSession = Depends(get_db)
) -> dict:
    """Give the principal role to someone already on staff, or create a new
    principal login. Do this only on a written request from the school or
    the department."""
    s = await _school(db, school_id)
    try:
        if body.existing_user_id:
            user = await onboarding.give_principal_role(db, s, body.existing_user_id)
            temp = None
        else:
            user, temp = await onboarding.add_first_login(db, s, body.display_name or "", "principal", body.staff_number)
    except onboarding.OnboardingError as e:
        raise onboarding.http_error(e)
    await _audit(db, staff, "principal.add", s.id, "user", user.id, {"new_login": temp is not None})
    await db.commit()
    return {"credentials": _credentials(user, temp, s) if temp else None, "name": user.display_name}


class RemoveRoleIn(BaseModel):
    switch_off: bool = False


@router.post("/schools/{school_id}/roles/{role_id}/remove")
async def remove_principal(
    school_id: uuid.UUID,
    role_id: uuid.UUID,
    body: RemoveRoleIn,
    staff: ConsoleStaff = Depends(require("lead")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    s = await _school(db, school_id)
    role = await db.get(StaffRole, role_id)
    if role is None or role.school_id != s.id:
        raise HTTPException(status_code=404, detail="No such role at this school.")
    try:
        user = await onboarding.remove_principal_role(db, role, body.switch_off)
    except onboarding.OnboardingError as e:
        raise onboarding.http_error(e)
    await _audit(db, staff, "principal.remove", s.id, "user", user.id if user else None, {"switched_off": body.switch_off})
    await db.commit()
    left = (await _counts(db, [s.id]))[s.id][2]
    return {"ok": True, "principals_left": left}


# --------------------------------------------------------------------------- registrations (lead)


def _reg_row(r: SchoolRegistration) -> dict:
    return {
        "id": str(r.id),
        "reference": str(r.id)[:8].upper(),
        "status": r.status,
        "school_name": r.school_name,
        "emis_number": r.emis_number,
        "province": r.province,
        "contact_name": r.contact_name,
        "contact_role": r.contact_role,
        "contact_cellphone": r.contact_cellphone,
        "contact_email": r.contact_email,
        "learner_estimate": r.learner_estimate,
        "message": r.message,
        "school_id": str(r.school_id) if r.school_id else None,
        "created_at": r.created_at.isoformat(),
        "decided_at": r.decided_at.isoformat() if r.decided_at else None,
    }


@router.get("/registrations")
async def list_registrations(staff: ConsoleStaff = Depends(require("lead")), db: AsyncSession = Depends(get_db)) -> dict:
    pending_first = case((SchoolRegistration.status == "pending", 0), else_=1)
    rows = (
        await db.execute(select(SchoolRegistration).order_by(pending_first, SchoolRegistration.created_at.desc()).limit(300))
    ).scalars().all()
    return {"registrations": [_reg_row(r) for r in rows]}


async def _registration(db, reg_id: uuid.UUID) -> SchoolRegistration:
    r = await db.get(SchoolRegistration, reg_id)
    if r is None:
        raise HTTPException(status_code=404, detail="No such request.")
    return r


class ApproveIn(BaseModel):
    as_role: str = "principal"
    staff_number: str | None = Field(default=None, max_length=50)


@router.post("/registrations/{reg_id}/approve")
async def approve_registration(
    reg_id: uuid.UUID, body: ApproveIn, staff: ConsoleStaff = Depends(require("lead")), db: AsyncSession = Depends(get_db)
) -> dict:
    """Only after confirming the school -- phone it on its official number and check the EMIS number."""
    reg = await _registration(db, reg_id)
    try:
        school, user, temp = await onboarding.approve_registration(db, reg, body.as_role, body.staff_number)
    except onboarding.OnboardingError as e:
        raise onboarding.http_error(e)
    await _audit(db, staff, "registration.approve", school.id, "school", school.id, {"reference": str(reg.id)[:8].upper()})
    await _audit(db, staff, "principal.add" if body.as_role == "principal" else "staff.create", school.id, "user", user.id,
                 {"role": body.as_role})
    await db.commit()
    return {"registration": _reg_row(reg), "credentials": _credentials(user, temp, school)}


@router.post("/registrations/{reg_id}/reject")
async def reject_registration(
    reg_id: uuid.UUID, staff: ConsoleStaff = Depends(require("lead")), db: AsyncSession = Depends(get_db)
) -> dict:
    reg = await _registration(db, reg_id)
    try:
        onboarding.reject_registration(reg)
    except onboarding.OnboardingError as e:
        raise onboarding.http_error(e)
    await _audit(db, staff, "registration.reject", None, "registration", reg.id, {"school": reg.school_name})
    await db.commit()
    return {"registration": _reg_row(reg)}


# --------------------------------------------------------------------------- INSIGHTS structure and officials (lead)


@router.get("/insights")
async def insights_structure(staff: ConsoleStaff = Depends(require("lead")), db: AsyncSession = Depends(get_db)) -> dict:
    districts = (await db.execute(select(District).order_by(District.name))).scalars().all()
    circuits = (await db.execute(select(Circuit).order_by(Circuit.name))).scalars().all()
    schools = (await db.execute(select(School.id, School.name, School.circuit_id).where(School.kind == "school").order_by(School.name))).all()
    officials = (
        await db.execute(
            select(User, OfficialAssignment)
            .join(OfficialAssignment, OfficialAssignment.user_id == User.id)
            .where(User.role == "official", User.is_active.is_(True))
            .order_by(User.display_name)
        )
    ).all()
    offices = {s.id: s.name for s in (await db.execute(select(School).where(School.kind == "office"))).scalars()}

    def off(level_field, level_id):
        return [
            {"user_id": str(u.id), "name": u.display_name, "login": u.student_number, "office": offices.get(u.school_id)}
            for u, a in officials
            if getattr(a, level_field) == level_id
        ]

    return {
        "districts": [
            {
                "id": str(d.id),
                "name": d.name,
                "province": d.province,
                "officials": off("district_id", d.id),
                "circuits": [
                    {
                        "id": str(c.id),
                        "name": c.name,
                        "officials": off("circuit_id", c.id),
                        "schools": [{"id": str(sid), "name": n} for sid, n, cid in schools if cid == c.id],
                    }
                    for c in circuits
                    if c.district_id == d.id
                ],
            }
            for d in districts
        ],
        "unplaced_schools": [{"id": str(sid), "name": n} for sid, n, cid in schools if cid is None],
    }


class DistrictIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    province: str = Field(min_length=2, max_length=60)


@router.post("/districts", status_code=201)
async def add_district(body: DistrictIn, staff: ConsoleStaff = Depends(require("lead")), db: AsyncSession = Depends(get_db)) -> dict:
    d = District(name=body.name.strip(), province=body.province.strip())
    db.add(d)
    await db.flush()
    await _audit(db, staff, "district.add", None, "district", d.id, {"name": d.name})
    await db.commit()
    return {"id": str(d.id)}


class CircuitIn(BaseModel):
    district_id: uuid.UUID
    name: str = Field(min_length=2, max_length=120)


@router.post("/circuits", status_code=201)
async def add_circuit(body: CircuitIn, staff: ConsoleStaff = Depends(require("lead")), db: AsyncSession = Depends(get_db)) -> dict:
    if await db.get(District, body.district_id) is None:
        raise HTTPException(status_code=404, detail="No such district.")
    c = Circuit(district_id=body.district_id, name=body.name.strip())
    db.add(c)
    await db.flush()
    await _audit(db, staff, "circuit.add", None, "circuit", c.id, {"name": c.name})
    await db.commit()
    return {"id": str(c.id)}


class PlaceIn(BaseModel):
    circuit_id: uuid.UUID | None = None  # None takes the school out of its circuit


@router.post("/schools/{school_id}/circuit")
async def place_school(
    school_id: uuid.UUID, body: PlaceIn, staff: ConsoleStaff = Depends(require("lead")), db: AsyncSession = Depends(get_db)
) -> dict:
    s = await _school(db, school_id)
    c = await db.get(Circuit, body.circuit_id) if body.circuit_id else None
    if body.circuit_id and c is None:
        raise HTTPException(status_code=404, detail="No such circuit.")
    s.circuit_id = c.id if c else None
    await _audit(db, staff, "school.circuit", s.id, "school", s.id, {"circuit": c.name if c else None})
    await db.commit()
    return {"ok": True}


class OfficialIn(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    circuit_id: uuid.UUID | None = None
    district_id: uuid.UUID | None = None


@router.post("/officials", status_code=201)
async def add_official(body: OfficialIn, staff: ConsoleStaff = Depends(require("lead")), db: AsyncSession = Depends(get_db)) -> dict:
    """Only under a signed agreement with the department (ADR-039)."""
    circuit = await db.get(Circuit, body.circuit_id) if body.circuit_id else None
    district = await db.get(District, body.district_id) if body.district_id else None
    try:
        user, office, temp = await onboarding.add_official(db, body.name, circuit=circuit, district=district)
    except onboarding.OnboardingError as e:
        raise onboarding.http_error(e)
    area = (circuit or district).name
    await _audit(db, staff, "official.add", None, "user", user.id, {"name": user.display_name, "area": area})
    await db.commit()
    return {"credentials": _credentials(user, temp, office), "area": area}


@router.post("/officials/{user_id}/remove")
async def remove_official(user_id: uuid.UUID, staff: ConsoleStaff = Depends(require("lead")), db: AsyncSession = Depends(get_db)) -> dict:
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="No such official.")
    try:
        await onboarding.remove_official(db, user)
    except onboarding.OnboardingError as e:
        raise onboarding.http_error(e)
    await _audit(db, staff, "official.remove", None, "user", user.id, {"name": user.display_name})
    await db.commit()
    return {"ok": True}


# --------------------------------------------------------------------------- audit (lead)

ACTION_LABELS = {
    "console.login": "Signed in",
    "console.2fa_setup": "Set up the authenticator app",
    "console.password": "Changed their password",
    "ticket.reply": "Replied to a ticket",
    "ticket.resolve": "Replied and resolved a ticket",
    "ticket.priority": "Changed a ticket's priority",
    "ticket.status": "Changed a ticket's status",
    "school.create": "Set up a school",
    "registration.approve": "Approved a school's registration",
    "registration.reject": "Rejected a school's registration",
    "principal.add": "Added a principal",
    "principal.remove": "Removed a principal role",
    "staff.create": "Created a first staff login",
    "school.circuit": "Placed a school in a circuit",
    "district.add": "Added a district",
    "circuit.add": "Added a circuit",
    "official.add": "Added an education official",
    "official.remove": "Removed an education official",
    "console_staff.create": "Added Console staff",
    "console_staff.role": "Changed a Console staff role",
    "console_staff.active": "Switched a Console login on or off",
    "console_staff.reset_2fa": "Reset someone's authenticator",
    "console_staff.reset_password": "Reset a Console password",
}


@router.get("/audit")
async def audit_log(
    limit: int = 200, staff: ConsoleStaff = Depends(require("lead")), db: AsyncSession = Depends(get_db)
) -> dict:
    rows = (
        await db.execute(
            select(AuditEvent, ConsoleStaff.display_name, School.name)
            .join(ConsoleStaff, ConsoleStaff.id == AuditEvent.console_staff_id)
            .outerjoin(School, School.id == AuditEvent.school_id)
            .order_by(AuditEvent.created_at.desc())
            .limit(max(1, min(limit, 1000)))
        )
    ).all()
    return {
        "events": [
            {
                "at": e.created_at.isoformat(),
                "by": who,
                "action": e.action,
                "label": ACTION_LABELS.get(e.action, e.action),
                "school": school,
                "target_type": e.target_type,
                "target_id": e.target_id,
                "details": e.details or {},
            }
            for e, who, school in rows
        ]
    }


# --------------------------------------------------------------------------- Console staff (director)


def _staff_row(s: ConsoleStaff) -> dict:
    return {
        **_me(s),
        "active": s.is_active,
        "authenticator_set_up": s.totp_confirmed,
        "last_login_at": s.last_login_at.isoformat() if s.last_login_at else None,
    }


@router.get("/staff")
async def list_staff(staff: ConsoleStaff = Depends(require("director")), db: AsyncSession = Depends(get_db)) -> dict:
    rows = (await db.execute(select(ConsoleStaff).order_by(ConsoleStaff.display_name))).scalars().all()
    return {"staff": [_staff_row(s) for s in rows], "roles": [{"id": r, "label": ROLE_LABEL[r]} for r in ROLES]}


class StaffIn(BaseModel):
    email: str = Field(min_length=5, max_length=200)
    display_name: str = Field(min_length=2, max_length=100)
    role: str = "agent"


@router.post("/staff", status_code=201)
async def create_staff(body: StaffIn, staff: ConsoleStaff = Depends(require("director")), db: AsyncSession = Depends(get_db)) -> dict:
    email = body.email.strip().lower()
    if "@" not in email:
        raise HTTPException(status_code=400, detail="Give a valid email address.")
    if body.role not in ROLES:
        raise HTTPException(status_code=400, detail="Unknown role")
    if (await db.execute(select(ConsoleStaff.id).where(ConsoleStaff.email == email))).first():
        raise HTTPException(status_code=400, detail="Someone already uses that email.")
    temp = generate_temp_password(14)
    new = ConsoleStaff(email=email, display_name=body.display_name.strip(), role=body.role, password_hash=hash_password(temp))
    db.add(new)
    await db.flush()
    await _audit(db, staff, "console_staff.create", None, "console_staff", new.id, {"email": email, "role": body.role})
    await db.commit()
    return {"staff": _staff_row(new), "temp_password": temp}


async def _other_staff(db, staff: ConsoleStaff, staff_id: uuid.UUID) -> ConsoleStaff:
    other = await db.get(ConsoleStaff, staff_id)
    if other is None:
        raise HTTPException(status_code=404, detail="No such person.")
    if other.id == staff.id:
        raise HTTPException(status_code=400, detail="You can't change your own access. Ask another director.")
    return other


async def _directors_left_without(db, other: ConsoleStaff) -> int:
    return (
        await db.execute(
            select(func.count()).select_from(ConsoleStaff).where(
                ConsoleStaff.role == "director", ConsoleStaff.is_active.is_(True), ConsoleStaff.id != other.id
            )
        )
    ).scalar_one()


class StaffChangeIn(BaseModel):
    role: str | None = None
    active: bool | None = None


@router.post("/staff/{staff_id}")
async def change_staff(
    staff_id: uuid.UUID, body: StaffChangeIn, staff: ConsoleStaff = Depends(require("director")), db: AsyncSession = Depends(get_db)
) -> dict:
    other = await _other_staff(db, staff, staff_id)
    losing_director = other.role == "director" and ((body.role and body.role != "director") or body.active is False)
    if losing_director and await _directors_left_without(db, other) == 0:
        raise HTTPException(status_code=400, detail="THUTOra Console must keep at least one active director.")
    if body.role is not None:
        if body.role not in ROLES:
            raise HTTPException(status_code=400, detail="Unknown role")
        await _audit(db, staff, "console_staff.role", None, "console_staff", other.id, {"from": other.role, "to": body.role})
        other.role = body.role
        other.token_version += 1
    if body.active is not None:
        await _audit(db, staff, "console_staff.active", None, "console_staff", other.id, {"active": body.active})
        other.is_active = body.active
        other.token_version += 1
    await db.commit()
    return {"staff": _staff_row(other)}


@router.post("/staff/{staff_id}/reset-authenticator")
async def reset_authenticator(
    staff_id: uuid.UUID, staff: ConsoleStaff = Depends(require("director")), db: AsyncSession = Depends(get_db)
) -> dict:
    """For a lost phone: they set up the app again at their next sign-in."""
    other = await _other_staff(db, staff, staff_id)
    other.totp_secret = None
    other.totp_confirmed = False
    other.totp_last_step = None
    other.token_version += 1
    await _audit(db, staff, "console_staff.reset_2fa", None, "console_staff", other.id)
    await db.commit()
    return {"staff": _staff_row(other)}


@router.post("/staff/{staff_id}/reset-password")
async def reset_staff_password(
    staff_id: uuid.UUID, staff: ConsoleStaff = Depends(require("director")), db: AsyncSession = Depends(get_db)
) -> dict:
    other = await _other_staff(db, staff, staff_id)
    temp = generate_temp_password(14)
    other.password_hash = hash_password(temp)
    other.must_change_password = True
    other.token_version += 1
    await _audit(db, staff, "console_staff.reset_password", None, "console_staff", other.id)
    await db.commit()
    return {"staff": _staff_row(other), "temp_password": temp}

