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
