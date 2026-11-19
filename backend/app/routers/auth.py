"""
POST /auth/login, GET /auth/me, POST /auth/change-password.
See docs/ADR-017-student-login.md.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user, get_current_user_allow_password_change
from app.models import Learner, School, User
from app.schemas.auth import (
    ChangePasswordRequest,
    HomeLanguageUpdate,
    LearnerProfile,
    LoginRequest,
    LoginResponse,
    MeResponse,
    SchoolProfile,
)
from app.core.security import get_current_learner
from app.services import login_throttle
from app.services.personalization import HOME_LANGUAGES
from app.services.auth import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


def _learner_profile(learner: Learner) -> LearnerProfile:
    return LearnerProfile(
        id=learner.id,
        display_name=learner.display_name,
        grade=learner.grade,
        preferred_modality=learner.preferred_modality,
        home_language=learner.home_language,
    )


@router.post("/login", response_model=LoginResponse)
async def login(
    payload: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)
) -> LoginResponse:
    # NEW 17 Nov 2026 (code review #6): refuse quickly while this login (or
    # this IP) is locked out after repeated wrong passwords.
    ip = request.client.host if request.client else None
    # deep scan M2: the browser's own random device id, so a lock only
    # affects the device the wrong passwords came from
    device = (request.headers.get("x-device-id") or "")[:64] or None
    wait, kind = await login_throttle.retry_after_seconds(db, payload.school_id, payload.student_number, device, ip)
    if wait:
        minutes = max(1, round(wait / 60))
        where = "on this device " if kind == "device" else ""
        raise HTTPException(
            status_code=429,
            detail=(
                f"Too many wrong passwords {where}-- try again in about {minutes} minute(s). "
                "Forgotten your password? Your teacher can reset it."
            ),
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
        await login_throttle.record_failure(db, payload.school_id, payload.student_number, device, ip)
        await db.commit()  # keep the failure even though the request ends in a 401
        raise HTTPException(status_code=401, detail="Incorrect student number or password")
    await login_throttle.record_success(db, payload.school_id, payload.student_number, device, ip)
    await db.commit()

    school = await db.get(School, user.school_id)
    token = create_access_token(str(user.id), user.role, user.token_version)

    # NEW 15 Nov 2026 (ADR-024): a teacher User has no linked Learner at
    # all -- provision_teacher() never creates one -- so this branches
    # before the student-only "No learner profile linked" 404 below,
    # which would otherwise incorrectly fire for every teacher login.
    # UPDATED 19 Nov 2026 (ADR-038): parents have no Learner row either.
    if user.role in ("teacher", "parent", "official"):  # ADR-038/039: no Learner row
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


@router.get("/home-languages", response_model=list[str])
async def list_home_languages() -> list[str]:
    """NEW 19 Nov 2026 (ADR-035): the options for the learner's language setting."""
    return list(HOME_LANGUAGES)


@router.put("/me/home-language", response_model=LearnerProfile)
async def set_home_language(
    payload: HomeLanguageUpdate,
    learner: Learner = Depends(get_current_learner),
    db: AsyncSession = Depends(get_db),
) -> LearnerProfile:
    """
    NEW 19 Nov 2026 (ADR-035). The learner picks the language the tutor may
    also explain in. Teaching stays in English by default; see
    personalization.build_language_instructions.
    """
    value = payload.home_language
    if value and value not in HOME_LANGUAGES:
        raise HTTPException(status_code=400, detail="Unknown language")
    learner.home_language = None if value in (None, "", "English") else value
    await db.commit()
    return _learner_profile(learner)


@router.post("/refresh")
async def refresh_token(user: User = Depends(get_current_user)) -> dict:
    """
    NEW 19 Nov 2026 (code review 19 Nov #5). A fresh token for a session
    that is still valid, so an open app stays logged in while it's in use
    (the frontend renews every 30 minutes). A deactivated account, or one
    whose password changed, already fails get_current_user -- so this
    can't extend a revoked session.
    """
    return {"access_token": create_access_token(str(user.id), user.role, user.token_version or 0)}
