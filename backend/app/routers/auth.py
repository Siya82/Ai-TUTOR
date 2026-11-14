"""
POST /auth/login, GET /auth/me, POST /auth/change-password.
See docs/ADR-017-student-login.md.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_learner, get_current_user
from app.models import Learner, School, User
from app.schemas.auth import (
    ChangePasswordRequest,
    LearnerProfile,
    LoginRequest,
    LoginResponse,
    MeResponse,
    SchoolProfile,
)
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
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)) -> LoginResponse:
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
        raise HTTPException(status_code=401, detail="Incorrect student number or password")

    learner_result = await db.execute(select(Learner).where(Learner.user_id == user.id))
    learner = learner_result.scalar_one_or_none()
    if learner is None:
        raise HTTPException(status_code=404, detail="No learner profile linked to this account")

    school = await db.get(School, user.school_id)

    token = create_access_token(str(user.id), user.role)
    return LoginResponse(
        access_token=token,
        must_change_password=user.must_change_password,
        learner=_learner_profile(learner),
        school=SchoolProfile(id=school.id, name=school.name),
    )


@router.get("/me", response_model=MeResponse)
async def read_me(
    user: User = Depends(get_current_user),
    learner: Learner = Depends(get_current_learner),
    db: AsyncSession = Depends(get_db),
) -> MeResponse:
    """Lets the frontend re-hydrate a stored token on page load without re-sending the password."""
    school = await db.get(School, user.school_id)
    return MeResponse(
        learner=_learner_profile(learner),
        school=SchoolProfile(id=school.id, name=school.name),
        must_change_password=user.must_change_password,
    )


@router.post("/change-password")
async def change_password(
    payload: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=401, detail="Current password is incorrect")
    user.password_hash = hash_password(payload.new_password)
    user.must_change_password = False
    await db.commit()
    return {"status": "ok"}
