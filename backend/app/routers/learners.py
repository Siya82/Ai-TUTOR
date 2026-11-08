"""
GET /learners -- lists every seeded learner, for the frontend to pick a
dev learner id from, with no hardcoded UUID.

NEW 8 Nov 2026, part of step 7. See app/schemas/learners.py's docstring
for the no-auth caveat -- this is pre-auth (step 8) dev-stage behavior
only, matching the rest of this API's current state.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models import Learner
from app.schemas.learners import LearnerResponse

router = APIRouter(prefix="/learners", tags=["learners"])


@router.get("/", response_model=list[LearnerResponse])
async def list_learners(db: AsyncSession = Depends(get_db)) -> list[Learner]:
    """All seeded learners, ordered by display name."""
    result = await db.execute(select(Learner).order_by(Learner.display_name))
    return list(result.scalars().all())
