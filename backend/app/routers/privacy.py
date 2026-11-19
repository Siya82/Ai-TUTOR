"""
NEW 19 Nov 2026 (ADR-037, POPIA basics).

GET    /privacy/notice-version                      -- current notice version (public)
GET    /school/learners/{id}/consent                -- consent history
POST   /school/learners/{id}/consent                -- record a parent's consent
POST   /school/learners/{id}/consent/withdraw       -- record that it was withdrawn
GET    /school/learners/{id}/export                 -- all data held on the learner (JSON)
DELETE /school/learners/{id}                        -- delete the learner and all their data

Recording consent: school management, or a teacher with the learner on
their roster (class teachers usually collect the forms). Export and
delete: school management only, and delete must repeat the learner's
name (typed in the confirmation box) so it can't happen by a mis-click.
"""

import json
import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.audit import record as audit  # code review 19 Nov #11
from app.core.clock import utcnow_naive
from app.core.database import get_db
from app.core.security import get_current_staff_scope
from app.models import ConsentRecord, Learner, User
from app.services.privacy import (
    PRIVACY_NOTICE_VERSION,
    delete_learner_data,
    export_learner_data,
    remove_files,
)
from app.services.school_scope import StaffScope

router = APIRouter(tags=["privacy"])


class ConsentIn(BaseModel):
    given_by_name: str = Field(min_length=1, max_length=100)
    relationship_to_learner: str = Field(min_length=1, max_length=50)
    method: Literal["signed_form", "parent_portal", "other"] = "signed_form"


class ConsentOut(BaseModel):
    id: uuid.UUID
    given_by_name: str
    relationship_to_learner: str
    method: str
    notice_version: str
    recorded_at: datetime | None
    withdrawn_at: datetime | None


class DeleteRequest(BaseModel):
    confirm_name: str = Field(min_length=1, max_length=100)


def _out(c: ConsentRecord) -> ConsentOut:
    return ConsentOut(
        id=c.id,
        given_by_name=c.given_by_name,
        relationship_to_learner=c.relationship_to_learner,
        method=c.method,
        notice_version=c.notice_version,
        recorded_at=c.recorded_at,
        withdrawn_at=c.withdrawn_at,
    )


async def _learner_in_school(db: AsyncSession, learner_id: uuid.UUID, scope: StaffScope) -> Learner:
    row = (
        await db.execute(
            select(Learner)
            .join(User, Learner.user_id == User.id)
            .where(Learner.id == learner_id, User.school_id == scope.school_id)
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Learner not found")
    return row


def _may_record(scope: StaffScope, learner: Learner) -> bool:
    return scope.can_manage_school or scope.can_see_roster(learner.id)


@router.get("/privacy/notice-version")
async def notice_version() -> dict:
    return {"version": PRIVACY_NOTICE_VERSION}


@router.get("/school/learners/{learner_id}/consent", response_model=list[ConsentOut])
async def list_consent(
    learner_id: uuid.UUID,
    scope: StaffScope = Depends(get_current_staff_scope),
    db: AsyncSession = Depends(get_db),
) -> list[ConsentOut]:
    learner = await _learner_in_school(db, learner_id, scope)
    if not _may_record(scope, learner):
        raise HTTPException(status_code=404, detail="Learner not found")
    rows = (
        await db.execute(
            select(ConsentRecord)
            .where(ConsentRecord.learner_id == learner.id)
            .order_by(ConsentRecord.recorded_at.desc())
        )
    ).scalars().all()
    return [_out(c) for c in rows]


@router.post("/school/learners/{learner_id}/consent", response_model=ConsentOut)
async def record_consent(
    learner_id: uuid.UUID,
    payload: ConsentIn,
    scope: StaffScope = Depends(get_current_staff_scope),
    db: AsyncSession = Depends(get_db),
) -> ConsentOut:
    learner = await _learner_in_school(db, learner_id, scope)
    if not _may_record(scope, learner):
        raise HTTPException(status_code=404, detail="Learner not found")
    record = ConsentRecord(
        learner_id=learner.id,
        given_by_name=payload.given_by_name.strip(),
        relationship_to_learner=payload.relationship_to_learner.strip(),
        method=payload.method,
        notice_version=PRIVACY_NOTICE_VERSION,
        recorded_by_user_id=scope.user_id,
    )
    db.add(record)
    await audit(db, scope.user_id, scope.school_id, "consent.record", "learner", learner.id, {"method": payload.method})
    await db.commit()
    return _out(record)


@router.post("/school/learners/{learner_id}/consent/withdraw", status_code=204)
async def withdraw_consent(
    learner_id: uuid.UUID,
    scope: StaffScope = Depends(get_current_staff_scope),
    db: AsyncSession = Depends(get_db),
) -> None:
    learner = await _learner_in_school(db, learner_id, scope)
    if not _may_record(scope, learner):
        raise HTTPException(status_code=404, detail="Learner not found")
    active = (
        await db.execute(
            select(ConsentRecord).where(
                ConsentRecord.learner_id == learner.id, ConsentRecord.withdrawn_at.is_(None)
            )
        )
    ).scalars().all()
    for c in active:
        c.withdrawn_at = utcnow_naive()
    await audit(db, scope.user_id, scope.school_id, "consent.withdraw", "learner", learner.id)
    await db.commit()


@router.get("/school/learners/{learner_id}/export")
async def export_learner(
    learner_id: uuid.UUID,
    scope: StaffScope = Depends(get_current_staff_scope),
    db: AsyncSession = Depends(get_db),
) -> Response:
    if not scope.can_manage_school:
        raise HTTPException(status_code=403, detail="Only school management can export a learner's data")
    learner = await _learner_in_school(db, learner_id, scope)
    data = await export_learner_data(db, learner)
    await audit(db, scope.user_id, scope.school_id, "privacy.export", "learner", learner.id)
    await db.commit()
    safe = "".join(ch if ch.isalnum() else "_" for ch in learner.display_name)[:40] or "learner"
    return Response(
        content=json.dumps(data, indent=2, ensure_ascii=False),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="thutora_{safe}.json"'},
    )


@router.delete("/school/learners/{learner_id}")
async def delete_learner(
    learner_id: uuid.UUID,
    payload: DeleteRequest,
    scope: StaffScope = Depends(get_current_staff_scope),
    db: AsyncSession = Depends(get_db),
) -> dict:
    if not scope.can_manage_school:
        raise HTTPException(status_code=403, detail="Only school management can delete a learner's data")
    learner = await _learner_in_school(db, learner_id, scope)
    if payload.confirm_name.strip().lower() != learner.display_name.strip().lower():
        raise HTTPException(status_code=400, detail="The name you typed doesn't match this learner")
    counts, paths = await delete_learner_data(db, learner)
    await audit(db, scope.user_id, scope.school_id, "privacy.delete", "learner", learner.id, counts)
    await db.commit()
    remove_files(paths)
    return {"deleted": True, **counts}
