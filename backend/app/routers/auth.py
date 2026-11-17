"""
POST /auth/login, GET /auth/me, POST /auth/change-password.
See docs/ADR-017-student-login.md.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user_allow_password_change
from app.models import Learner, School, User
from app.schemas.auth import (
    ChangePasswordRequest,
    LearnerProfile,
    LoginRequest,
    LoginResponse,
    MeResponse,
    SchoolProfile,
)
from app.services import login_throttle
from app.services.auth import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


def _learner_profile(learner: Learner) -> LearnerProfile:
    return LearnerProfile(
        id=learner.id,
        display_name=learner.display_name,
        grade=learner.grade,
        preferred_modality=learner.preferred_modality,
    )


@router.post("/login", response_model=LoginResponse)
async def login(
    payload: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)
) -> LoginResponse:
    # NEW 17 Nov 2026 (code review #6): refuse quickly while this login (or
    # this IP) is locked out after repeated wrong passwords.
    ip = request.client.host if request.client else None
    wait = login_throttle.retry_after_seconds(payload.school_id, payload.student_number, ip)
    if wait:
        minutes = max(1, round(wait / 60))
        raise HTTPException(
            status_code=429,
            detail=f"Too many wrong passwords. Try again in about {minutes} minute(s).",
            headers={"Retry-After": str(wait)},
        )
    stmt = select(User).where(
        User.school_id == payload.school_id, User.student_number == payload.student_number
    )
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    # Same error for "no such student number at this school" and "wrong
    # password" -- never reveal which one it was; standard login-endpoint
    # practice, and doubly worth it here since school_id + student_number
    # together are a guessable identifier, not a secret.
    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
        login_throttle.record_failure(payload.school_id, payload.student_number, ip)
        raise HTTPException(status_code=401, detail="Incorrect student number or password")
    login_throttle.record_success(payload.school_id, payload.student_number)

    school = await db.get(School, user.school_id)
    token = create_access_token(str(user.id), user.role, user.token_version)

    # NEW 15 Nov 2026 (ADR-024): a teacher User has no linked Learner at
    # all -- provision_teacher() never creates one -- so this branches
    # before the student-only "No learner profile linked" 404 below,
    # which would otherwise incorrectly fire for every teacher login.
    if user.role == "teacher":
        return LoginResponse(
            access_token=token,
            must_change_password=user.must_change_password,
            role=user.role,
            learner=None,
            school=SchoolProfile(id=school.id, name=school.name),
        )

    learner_result = await db.execute(select(Learner).where(Learner.user_id == user.id))
    learner = learner_result.scalar_one_or_none()
    if learner is None:
        raise HTTPException(status_code=404, detail="No learner profile linked to this account")

    return LoginResponse(
        access_token=token,
        must_change_password=user.must_change_password,
        role=user.role,
        learner=_learner_profile(learner),
        school=SchoolProfile(id=school.id, name=school.name),
    )


@router.get("/me", response_model=MeResponse)
async def read_me(
    user: User = Depends(get_current_user_allow_password_change),
    db: AsyncSession = Depends(get_db),
) -> MeResponse:
    """
    Lets the frontend re-hydrate a stored token on page load without
    re-sending the password.

    FIX 15 Nov 2026 (ADR-024): no longer depends on get_current_learner
    directly -- that dependency 404s outright for a teacher User (which
    has no Learner row at all), which would have broken page-refresh
    for every teacher session. The learner lookup now happens inline
    here instead, and is allowed to come back empty for a non-student
    role.
    """
    school = await db.get(School, user.school_id)
    learner_profile = None
    if user.role != "teacher":
        learner_result = await db.execute(select(Learner).where(Learner.user_id == user.id))
        learner = learner_result.scalar_one_or_none()
        if learner is not None:
            learner_profile = _learner_profile(learner)
    return MeResponse(
        role=user.role,
        learner=learner_profile,
        school=SchoolProfile(id=school.id, name=school.name),
        must_change_password=user.must_change_password,
    )


@router.post("/change-password")
async def change_password(
    payload: ChangePasswordRequest,
    user: User = Depends(get_current_user_allow_password_change),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    UPDATED 17 Nov 2026 (code review #6): bumps token_version, so every
    other session for this account ends, and returns a fresh token for
    the one that changed it (the frontend swaps it in).
    """
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=401, detail="Current password is incorrect")
    user.password_hash = hash_password(payload.new_password)
    user.must_change_password = False
    user.token_version = (user.token_version or 0) + 1
    await db.commit()
    return {
        "status": "ok",
        "access_token": create_access_token(str(user.id), user.role, user.token_version),
    }
