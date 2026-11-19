"""
GET /schools -- lists schools (id, name, kind) for the login screen's school
picker. No auth (a student has to be able to find their own school before
they can log in at all) and deliberately exposes nothing beyond name and
kind -- see docs/ADR-017-student-login.md.

UPDATED 19 Nov 2026 (code review 19 Nov #12): a national roll-out means
thousands of schools, so the picker now SEARCHES (?q=, at most 20 results)
instead of loading one giant list, and GET /schools/{id} lets the app show
the school this device used last time. Without ?q the full list is still
returned (small deployments, scripts), capped at 500.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models import School

router = APIRouter(prefix="/schools", tags=["schools"])


def _out(s: School) -> dict:
    return {"id": str(s.id), "name": s.name, "kind": s.kind, "province": s.province}


@router.get("/")
async def list_schools(
    q: str | None = Query(default=None, max_length=100),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    stmt = select(School)
    if q and q.strip():
        term = q.strip()
        # names that START with what was typed come first
        stmt = (
            stmt.where(School.name.ilike(f"%{term}%") | (School.emis_number == term))
            .order_by(case((School.name.ilike(f"{term}%"), 0), else_=1), School.name)
            .limit(20)
        )
    else:
        stmt = stmt.order_by(School.kind.desc(), School.name).limit(500)  # schools before offices
    return [_out(s) for s in (await db.execute(stmt)).scalars().all()]


@router.get("/{school_id}")
async def get_school(school_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> dict:
    school = await db.get(School, school_id)
    if school is None:
        raise HTTPException(status_code=404, detail="School not found")
    return _out(school)
