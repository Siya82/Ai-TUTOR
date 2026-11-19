"""
NEW 19 Nov 2026 (ADR-043): verifying parents, guardian contacts, viewers.

School staff (management, or the learner's own teacher):
  GET    /school/learners/{id}/guardians            -- contacts the school holds
  POST   /school/learners/{id}/guardians            -- add one
  PUT    /school/learners/{id}/guardians/{gid}      -- correct one
  DELETE /school/learners/{id}/guardians/{gid}      -- remove one

Parent self-sign-up (public; only works against the school's own records):
  GET  /connect/signup/available
  POST /connect/signup/start    {school_id, cellphone}       -> SMS code if on record
  POST /connect/signup/verify   {school_id, cellphone, code, password, full_name?}

Viewers (a guardian invites e.g. a grandparent):
  GET    /parent/children/{id}/viewers
  POST   /parent/children/{id}/viewers/invite   {viewer_name, relationship}
  DELETE /parent/children/{id}/viewers/{user_id}
  POST   /connect/viewer/redeem   {school_id, code, password}   (public)
"""

import logging
import time
import uuid
from collections import defaultdict, deque
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utcnow_naive
from app.core.database import get_db
from app.core.security import get_current_staff_scope
from app.models import Learner, LearnerGuardian, ParentLink, School, SignupCode, User, ViewerInvite
from app.routers.connect import get_current_parent
from app.services.auth import _generate_unique_login_number, create_access_token, hash_password
from app.services.family import (
    INVITE_DAYS,
    OTP_MAX_ATTEMPTS,
    OTP_MINUTES,
    invite_hash,
    local_format,
    new_invite_code,
    new_otp,
    normalize_sa_cellphone,
    otp_matches,
)
from app.services.school_scope import StaffScope
from app.services.sms import SmsUnavailable, send_sms, sms_enabled

router = APIRouter(tags=["family"])
log = logging.getLogger("thutora.family")

GENERIC_START_REPLY = (
    "If this number is on the school's records, we've sent an SMS with a 6-digit code. "
    "No SMS? Ask the school to check the cellphone number they have for you."
)

# Simple in-memory limits on sending codes (per number and per IP, per hour).
_sent_by_number: dict[str, deque] = defaultdict(deque)
_sent_by_ip: dict[str, deque] = defaultdict(deque)


def _allow_send(key: str, ip: str | None) -> bool:
    now = time.monotonic()
    for bucket, k, limit in ((_sent_by_number, key, 3), (_sent_by_ip, ip or "-", 20)):
        q = bucket[k]
        while q and now - q[0] > 3600:
            q.popleft()
        if len(q) >= limit:
            return False
    _sent_by_number[key].append(now)
    _sent_by_ip[ip or "-"].append(now)
    return True


# --- schemas -------------------------------------------------------------------


class GuardianIn(BaseModel):
    full_name: str = Field(min_length=1, max_length=100)
    relationship_to_learner: str = Field(default="Parent", min_length=1, max_length=50)
    cellphone: str | None = Field(default=None, max_length=30)
    email: str | None = Field(default=None, max_length=200)


class SignupStart(BaseModel):
    school_id: uuid.UUID
    cellphone: str = Field(min_length=9, max_length=30)


class SignupVerify(BaseModel):
    school_id: uuid.UUID
    cellphone: str = Field(min_length=9, max_length=30)
    code: str = Field(min_length=4, max_length=10)
    password: str = Field(min_length=8, max_length=72)
    full_name: str | None = Field(default=None, max_length=100)


class ViewerInviteIn(BaseModel):
    viewer_name: str = Field(min_length=1, max_length=100)
    relationship: str = Field(default="Grandparent", min_length=1, max_length=50)


class ViewerRedeem(BaseModel):
    school_id: uuid.UUID
    code: str = Field(min_length=6, max_length=20)
    password: str = Field(min_length=8, max_length=72)


# --- school staff: guardian contacts -----------------------------------------------


async def _staff_learner(db: AsyncSession, learner_id: uuid.UUID, scope: StaffScope) -> Learner:
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


def _guardian_out(g: LearnerGuardian) -> dict:
    return {
        "id": str(g.id),
        "full_name": g.full_name,
        "relationship": g.relationship_to_learner,
        "cellphone": local_format(g.cellphone) if g.cellphone else None,
        "email": g.email,
        "signed_up": g.parent_user_id is not None,
    }


def _clean_phone(raw: str | None) -> str | None:
    if not raw or not raw.strip():
        return None
    try:
        return normalize_sa_cellphone(raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/school/learners/{learner_id}/guardians")
async def list_guardians(
    learner_id: uuid.UUID, scope: StaffScope = Depends(get_current_staff_scope), db: AsyncSession = Depends(get_db)
) -> list[dict]:
    learner = await _staff_learner(db, learner_id, scope)
    rows = (
        await db.execute(
            select(LearnerGuardian).where(LearnerGuardian.learner_id == learner.id).order_by(LearnerGuardian.created_at)
        )
    ).scalars().all()
    return [_guardian_out(g) for g in rows]


@router.post("/school/learners/{learner_id}/guardians")
async def add_guardian(
    learner_id: uuid.UUID,
    payload: GuardianIn,
    scope: StaffScope = Depends(get_current_staff_scope),
    db: AsyncSession = Depends(get_db),
) -> dict:
    learner = await _staff_learner(db, learner_id, scope)
    g = LearnerGuardian(
        learner_id=learner.id,
        full_name=payload.full_name.strip(),
        relationship_to_learner=payload.relationship_to_learner.strip(),
        cellphone=_clean_phone(payload.cellphone),
        email=(payload.email or "").strip() or None,
        created_by_user_id=scope.user_id,
    )
    db.add(g)
    await db.commit()
    return _guardian_out(g)


@router.put("/school/learners/{learner_id}/guardians/{guardian_id}")
async def update_guardian(
    learner_id: uuid.UUID,
    guardian_id: uuid.UUID,
    payload: GuardianIn,
    scope: StaffScope = Depends(get_current_staff_scope),
    db: AsyncSession = Depends(get_db),
) -> dict:
    learner = await _staff_learner(db, learner_id, scope)
    g = await db.get(LearnerGuardian, guardian_id)
    if g is None or g.learner_id != learner.id:
        raise HTTPException(status_code=404, detail="Contact not found")
    g.full_name = payload.full_name.strip()
    g.relationship_to_learner = payload.relationship_to_learner.strip()
    g.cellphone = _clean_phone(payload.cellphone)
    g.email = (payload.email or "").strip() or None
    await db.commit()
    return _guardian_out(g)


@router.delete("/school/learners/{learner_id}/guardians/{guardian_id}", status_code=204)
async def delete_guardian(
    learner_id: uuid.UUID,
    guardian_id: uuid.UUID,
    scope: StaffScope = Depends(get_current_staff_scope),
    db: AsyncSession = Depends(get_db),
) -> None:
    learner = await _staff_learner(db, learner_id, scope)
    await db.execute(
        delete(LearnerGuardian).where(LearnerGuardian.id == guardian_id, LearnerGuardian.learner_id == learner.id)
    )
    await db.commit()


# --- parent self-sign-up --------------------------------------------------------------


async def _matching_guardians(db: AsyncSession, school_id: uuid.UUID, cellphone: str) -> list[LearnerGuardian]:
    """Guardian contacts with this number, for ACTIVE learners at this school."""
    return (
        await db.execute(
            select(LearnerGuardian)
            .join(Learner, LearnerGuardian.learner_id == Learner.id)
            .join(User, Learner.user_id == User.id)
            .where(
                LearnerGuardian.cellphone == cellphone,
                User.school_id == school_id,
                User.is_active.is_(True),
            )
        )
    ).scalars().all()


@router.get("/connect/signup/available")
async def signup_available() -> dict:
    return {"enabled": sms_enabled()}


@router.post("/connect/signup/start")
async def signup_start(payload: SignupStart, request: Request, db: AsyncSession = Depends(get_db)) -> dict:
    if not sms_enabled():
        raise HTTPException(status_code=503, detail="Parent sign-up by SMS isn't available yet. Ask the school for a login.")
    try:
        phone = normalize_sa_cellphone(payload.cellphone)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    ip = request.client.host if request.client else None
    if not _allow_send(f"{payload.school_id}:{phone}", ip):
        raise HTTPException(status_code=429, detail="Too many codes requested. Please try again in an hour.")
    if await _matching_guardians(db, payload.school_id, phone):
        code, code_hash = new_otp()
        db.add(
            SignupCode(
                school_id=payload.school_id,
                cellphone=phone,
                code_hash=code_hash,
                expires_at=utcnow_naive() + timedelta(minutes=OTP_MINUTES),
            )
        )
        await db.commit()
        try:
            await send_sms(phone, f"Your THUTOra code is {code}. It expires in {OTP_MINUTES} minutes.")
        except SmsUnavailable:
            raise HTTPException(status_code=503, detail="SMS isn't available right now. Please try later.")
    # Same reply either way, so nobody can find out which numbers a school holds.
    return {"message": GENERIC_START_REPLY}


@router.post("/connect/signup/verify")
async def signup_verify(payload: SignupVerify, db: AsyncSession = Depends(get_db)) -> dict:
    try:
        phone = normalize_sa_cellphone(payload.cellphone)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    code_row = (
        await db.execute(
            select(SignupCode)
            .where(
                SignupCode.school_id == payload.school_id,
                SignupCode.cellphone == phone,
                SignupCode.used_at.is_(None),
            )
            .order_by(SignupCode.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    wrong = HTTPException(status_code=400, detail="That code is wrong or has expired. Request a new one.")
    if code_row is None or code_row.expires_at < utcnow_naive() or code_row.attempts >= OTP_MAX_ATTEMPTS:
        raise wrong
    if not otp_matches(payload.code, code_row.code_hash):
        code_row.attempts += 1
        await db.commit()
        raise wrong
    code_row.used_at = utcnow_naive()

    guardians = await _matching_guardians(db, payload.school_id, phone)
    if not guardians:
        await db.commit()
        raise HTTPException(status_code=400, detail="This number is no longer on the school's records.")
    login_number = local_format(phone)
    parent = (
        await db.execute(
            select(User).where(
                User.school_id == payload.school_id, User.role == "parent", User.student_number == login_number
            )
        )
    ).scalar_one_or_none()
    if parent is None:
        parent = User(
            role="parent",
            school_id=payload.school_id,
            student_number=login_number,
            display_name=(payload.full_name or "").strip() or guardians[0].full_name,
        )
        db.add(parent)
    elif not parent.is_active:
        raise HTTPException(status_code=403, detail="This parent login has been switched off by the school.")
    # A verified number also works as "forgot my password": the new password replaces the old.
    parent.password_hash = hash_password(payload.password)
    parent.must_change_password = False
    parent.token_version = (parent.token_version or 0) + 1
    await db.flush()
    linked = 0
    for g in guardians:
        g.parent_user_id = parent.id
        exists = (
            await db.execute(
                select(ParentLink).where(ParentLink.parent_user_id == parent.id, ParentLink.learner_id == g.learner_id)
            )
        ).scalar_one_or_none()
        if exists is None:
            db.add(
                ParentLink(
                    parent_user_id=parent.id,
                    learner_id=g.learner_id,
                    relationship_to_learner=g.relationship_to_learner,
                    kind="guardian",
                )
            )
        linked += 1
    await db.commit()
    school = await db.get(School, payload.school_id)
    log.info("Parent self-sign-up verified at school %s (%d learner(s))", payload.school_id, linked)
    return {
        "login_number": login_number,
        "children_linked": linked,
        "access_token": create_access_token(str(parent.id), parent.role, parent.token_version),
        "role": "parent",
        "school": {"id": str(school.id), "name": school.name} if school else None,
        "display_name": parent.display_name,
    }


# --- viewers -----------------------------------------------------------------------------


async def _guardian_link(db: AsyncSession, parent: User, learner_id: uuid.UUID) -> ParentLink:
    link = (
        await db.execute(
            select(ParentLink).where(
                ParentLink.parent_user_id == parent.id,
                ParentLink.learner_id == learner_id,
                ParentLink.kind == "guardian",
            )
        )
    ).scalar_one_or_none()
    if link is None:
        raise HTTPException(status_code=404, detail="Only a parent or guardian can manage family access")
    return link


@router.get("/parent/children/{learner_id}/viewers")
async def list_viewers(
    learner_id: uuid.UUID, parent: User = Depends(get_current_parent), db: AsyncSession = Depends(get_db)
) -> dict:
    await _guardian_link(db, parent, learner_id)
    viewers = (
        await db.execute(
            select(User, ParentLink.relationship_to_learner)
            .join(ParentLink, ParentLink.parent_user_id == User.id)
            .where(ParentLink.learner_id == learner_id, ParentLink.kind == "viewer")
        )
    ).all()
    pending = (
        await db.execute(
            select(ViewerInvite).where(
                ViewerInvite.learner_id == learner_id,
                ViewerInvite.used_at.is_(None),
                ViewerInvite.expires_at > utcnow_naive(),
            )
        )
    ).scalars().all()
    return {
        "viewers": [
            {"user_id": str(u.id), "name": u.display_name, "relationship": rel, "login_number": u.student_number}
            for u, rel in viewers
        ],
        "pending_invites": [
            {"name": i.viewer_name, "relationship": i.relationship_to_learner, "expires_at": i.expires_at.isoformat()}
            for i in pending
        ],
    }


@router.post("/parent/children/{learner_id}/viewers/invite")
async def invite_viewer(
    learner_id: uuid.UUID,
    payload: ViewerInviteIn,
    parent: User = Depends(get_current_parent),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await _guardian_link(db, parent, learner_id)
    code, code_hash = new_invite_code()
    db.add(
        ViewerInvite(
            school_id=parent.school_id,
            learner_id=learner_id,
            invited_by_user_id=parent.id,
            viewer_name=payload.viewer_name.strip(),
            relationship_to_learner=payload.relationship.strip(),
            code_hash=code_hash,
            expires_at=utcnow_naive() + timedelta(days=INVITE_DAYS),
        )
    )
    await db.commit()
    return {"code": code, "expires_in_days": INVITE_DAYS}


@router.delete("/parent/children/{learner_id}/viewers/{viewer_user_id}", status_code=204)
async def remove_viewer(
    learner_id: uuid.UUID,
    viewer_user_id: uuid.UUID,
    parent: User = Depends(get_current_parent),
    db: AsyncSession = Depends(get_db),
) -> None:
    await _guardian_link(db, parent, learner_id)
    await db.execute(
        delete(ParentLink).where(
            ParentLink.learner_id == learner_id,
            ParentLink.parent_user_id == viewer_user_id,
            ParentLink.kind == "viewer",
        )
    )
    await db.commit()


@router.post("/connect/viewer/redeem")
async def redeem_viewer_invite(payload: ViewerRedeem, db: AsyncSession = Depends(get_db)) -> dict:
    invite = (
        await db.execute(
            select(ViewerInvite).where(
                ViewerInvite.school_id == payload.school_id,
                ViewerInvite.code_hash == invite_hash(payload.code),
                ViewerInvite.used_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if invite is None or invite.expires_at < utcnow_naive():
        raise HTTPException(status_code=400, detail="That invite code is wrong, used or expired. Ask for a new one.")
    school = await db.get(School, payload.school_id)
    viewer = User(
        role="parent",
        school_id=payload.school_id,
        student_number=await _generate_unique_login_number(db, school),
        display_name=invite.viewer_name,
        password_hash=hash_password(payload.password),
        must_change_password=False,
    )
    db.add(viewer)
    await db.flush()
    db.add(
        ParentLink(
            parent_user_id=viewer.id,
            learner_id=invite.learner_id,
            relationship_to_learner=invite.relationship_to_learner,
            kind="viewer",
            invited_by_user_id=invite.invited_by_user_id,
        )
    )
    invite.used_at = utcnow_naive()
    await db.commit()
    return {
        "login_number": viewer.student_number,
        "access_token": create_access_token(str(viewer.id), viewer.role, viewer.token_version or 0),
        "role": "parent",
        "school": {"id": str(school.id), "name": school.name},
        "display_name": viewer.display_name,
    }
