"""
GET /schools -- lists every school (id, name only), for the login
screen's school picker. No auth (a student has to be able to find
their own school before they can log in at all) and deliberately
exposes nothing beyond name -- see docs/ADR-017-student-login.md.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models import School
from app.schemas.auth import SchoolProfile

router = APIRouter(prefix="/schools", tags=["schools"])


@router.get("/", response_model=list[SchoolProfile])
async def list_schools(db: AsyncSession = Depends(get_db)) -> list[School]:
    result = await db.execute(select(School).order_by(School.name))
    return list(result.scalars().all())
