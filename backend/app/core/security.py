"""
FastAPI auth dependencies: decode the bearer token, resolve the current
User, and resolve the current Learner. See docs/ADR-017-student-login.md.

Kept in app/core/ rather than app/routers/auth.py so the tutor/
attachments routers can depend on get_current_learner without a
router-importing-a-router relationship -- this module only depends on
app/services/auth.py (pure token logic) and app/models.
"""

import uuid

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models import Learner, User
from app.services.auth import decode_access_token


async def get_current_user(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Decodes the Bearer token, loads the User it names, and 401s on
    anything wrong (missing header, bad/expired token, deleted/
    deactivated user). This is the real boundary that replaces the old
    "trust whatever learner_id the request body says" posture
    (REBUILD_SPEC.md Section 2 step 8, ADR-017).
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = authorization.removeprefix("Bearer ").strip()
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    try:
        user_id = uuid.UUID(str(payload.get("sub", "")))
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return user


async def get_current_learner(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Learner:
    """
    The dependency app/routers/tutor.py and app/routers/attachments.py
    actually use: resolves straight to the authenticated student's own
    Learner row, so neither endpoint takes a learner_id from the
    request body anymore (ADR-017).
    """
    stmt = select(Learner).where(Learner.user_id == user.id)
    result = await db.execute(stmt)
    learner = result.scalar_one_or_none()
    if learner is None:
        raise HTTPException(status_code=404, detail="No learner profile linked to this account")
    return learner


async def get_current_learner_or_teacher(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> tuple[User, Learner | None]:
    """
    NEW 15 Nov 2026 (live-test finding, follow-up to ADR-026/ADR-028).
    ADR-026 locked GET /subjects and /topics down to get_current_learner
    alone -- correct for the student picker, but it then broke the
    teacher-side topic picker in CreateAssignmentForm (added right
    after, ADR-028): the first time this was actually live-tested, a
    teacher opening the Assignments tab got a bare "No learner profile
    linked to this account" 404, since a teacher has no Learner row at
    all.

    This dependency resolves either role: a student gets back their own
    Learner row exactly as get_current_learner always has (so ADR-026's
    grade filter is unaffected for them); a teacher gets back (user,
    None), so the caller knows to skip the grade filter entirely -- a
    teacher may reasonably author a question or build an assignment
    for a student in any grade they teach, not just one grade.
    """
    if user.role == "teacher":
        return user, None
    stmt = select(Learner).where(Learner.user_id == user.id)
    result = await db.execute(stmt)
    learner = result.scalar_one_or_none()
    if learner is None:
        raise HTTPException(status_code=404, detail="No learner profile linked to this account")
    return user, learner


async def get_current_teacher(user: User = Depends(get_current_user)) -> User:
    """
    NEW 15 Nov 2026 (ADR-024, teacher dashboard access + bulk student
    provisioning). The dependency app/routers/dashboard.py and
    app/routers/admin.py use to gate teacher-only endpoints -- resolves
    the same authenticated User as get_current_user, but 403s (not
    401 -- the token itself is perfectly valid, the role just isn't
    allowed on this endpoint) when its role isn't "teacher".
    Deliberately does NOT also resolve a Learner the way
    get_current_learner does, since a teacher doesn't have one at all.
    """
    if user.role != "teacher":
        raise HTTPException(status_code=403, detail="Teacher access required")
    return user


async def get_current_staff_scope(
    user: User = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    """
    NEW 17 Nov 2026 (ADR-031). A staff user's resolved scope -- which
    learners they may see (roster) and which subjects of each learner's
    data they may see and assign (academic). Every TEACH endpoint that
    returns or acts on learner data depends on this rather than on
    school_id alone. Imported lazily to keep app.core free of a
    services-level import cycle.
    """
    from app.services.school_scope import load_scope

    return await load_scope(db, user)
