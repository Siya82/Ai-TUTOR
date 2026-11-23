"""
NEW 23 Nov 2026 (ADR-050). THUTOra support.

  GET  /support/contact                      public: email, WhatsApp, hours
  POST /support/tickets                      staff and officials log a ticket
  GET  /support/tickets                      mine (school managers: the school's)
  GET  /support/tickets/{id}                 the ticket and its messages
  POST /support/tickets/{id}/messages        add a reply (reopens it)
  POST /support/tickets/{id}/resolve         the school marks it sorted

Zynora answers from scripts/support.py.
"""

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utcnow_naive
from app.core.database import get_db
from app.core.security import get_current_user
from app.models import School, SupportMessage, SupportTicket, User
from app.services import rate_limit
from app.services.school_scope import load_scope
from app.services.support import (
    CATEGORIES,
    PRIORITY_LABEL,
    SUPPORT_ROLES,
    alert_zynora,
    contact,
    priority_for,
)

router = APIRouter(prefix="/support", tags=["support"])
TICKETS_PER_DAY = 10


class TicketIn(BaseModel):
    product: Literal["teach", "admin", "insights"]
    category: str
    subject: str = Field(min_length=3, max_length=150)
    body: str = Field(min_length=5, max_length=4000)
    blocking: bool = False  # "a class can't work right now"
    screen: str = Field(default="", max_length=80)
    app_version: str = Field(default="", max_length=40)


class MessageIn(BaseModel):
    body: str = Field(min_length=1, max_length=4000)


async def _support_user(user: User = Depends(get_current_user)) -> User:
    if user.role not in SUPPORT_ROLES:
        raise HTTPException(
            status_code=403,
            detail="Please ask your teacher or school for help. They can sort out logins and contact THUTOra support.",
        )
    return user


async def _can_manage(db: AsyncSession, user: User) -> bool:
    return user.role == "teacher" and (await load_scope(db, user)).can_manage_school


async def _ticket_for(db: AsyncSession, user: User, ticket_id: uuid.UUID) -> SupportTicket:
    t = await db.get(SupportTicket, ticket_id)
    if t is None or t.school_id != user.school_id:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if t.created_by_user_id != user.id and not await _can_manage(db, user):
        raise HTTPException(status_code=404, detail="Ticket not found")
    return t


def _summary(t: SupportTicket, user: User) -> dict:
    return {
        "id": str(t.id),
        "number": t.number,
        "product": t.product,
        "category": t.category,
        "category_label": CATEGORIES.get(t.category, (t.category,))[0],
        "priority": t.priority,
        "priority_label": PRIORITY_LABEL.get(t.priority, t.priority),
        "subject": t.subject,
        "status": t.status,
        "mine": t.created_by_user_id == user.id,
        "created_at": t.created_at.isoformat(),
        "updated_at": t.updated_at.isoformat(),
    }


@router.get("/contact")
async def support_contact() -> dict:
    return {**contact(), "categories": [{"id": k, "label": v[0], "urgent": v[1] == "p1"} for k, v in CATEGORIES.items()]}


@router.post("/tickets", status_code=201)
async def create_ticket(body: TicketIn, user: User = Depends(_support_user), db: AsyncSession = Depends(get_db)) -> dict:
    if body.category not in CATEGORIES:
        raise HTTPException(status_code=422, detail="Unknown category")
    key = f"support:{user.id}"
    if await rate_limit.too_many(db, key, TICKETS_PER_DAY, 24 * 3600):
        raise HTTPException(status_code=429, detail="That's a lot of tickets today. Please email or WhatsApp support.")
    await rate_limit.hit(db, key)
    now = utcnow_naive()
    t = SupportTicket(
        school_id=user.school_id,
        created_by_user_id=user.id,
        product=body.product,
        category=body.category,
        priority=priority_for(body.category, body.blocking),
        subject=body.subject.strip(),
        status="open",
        context={"screen": body.screen, "app_version": body.app_version, "role": user.role},
        created_at=now,
        updated_at=now,
    )
    db.add(t)
    await db.flush()
    db.add(SupportMessage(ticket_id=t.id, author_user_id=user.id, body=body.body.strip(), created_at=now))
    await db.commit()
    await db.refresh(t)
    school = await db.get(School, user.school_id)
    await alert_zynora(
        f"[THUTOra #{t.number}] {PRIORITY_LABEL[t.priority]}: {t.subject}",
        f"School: {school.name if school else user.school_id}\nFrom: {user.student_number} ({user.role})\n"
        f"Product: {t.product}  Category: {CATEGORIES[t.category][0]}\n\n{body.body.strip()}\n\n"
        f"Reply with: python -m scripts.support reply {t.number} \"...\"",
        urgent=t.priority == "p1",
    )
    return _summary(t, user)


@router.get("/tickets")
async def list_tickets(user: User = Depends(_support_user), db: AsyncSession = Depends(get_db)) -> list[dict]:
    q = select(SupportTicket).where(SupportTicket.school_id == user.school_id)
    if not await _can_manage(db, user):
        q = q.where(SupportTicket.created_by_user_id == user.id)
    rows = (await db.execute(q.order_by(SupportTicket.updated_at.desc()).limit(200))).scalars().all()
    return [_summary(t, user) for t in rows]


@router.get("/tickets/{ticket_id}")
async def get_ticket(ticket_id: uuid.UUID, user: User = Depends(_support_user), db: AsyncSession = Depends(get_db)) -> dict:
    t = await _ticket_for(db, user, ticket_id)
    msgs = (
        await db.execute(select(SupportMessage).where(SupportMessage.ticket_id == t.id).order_by(SupportMessage.created_at))
    ).scalars().all()
    authors = {
        u.id: u.student_number
        for u in (
            await db.execute(select(User).where(User.id.in_([m.author_user_id for m in msgs if m.author_user_id])))
        ).scalars()
    }
    return {
        **_summary(t, user),
        "messages": [
            {
                "from_zynora": m.from_zynora,
                "author": "THUTOra support" if m.from_zynora else authors.get(m.author_user_id, "School"),
                "body": m.body,
                "created_at": m.created_at.isoformat(),
            }
            for m in msgs
        ],
    }


@router.post("/tickets/{ticket_id}/messages", status_code=201)
async def reply(
    ticket_id: uuid.UUID, body: MessageIn, user: User = Depends(_support_user), db: AsyncSession = Depends(get_db)
) -> dict:
    t = await _ticket_for(db, user, ticket_id)
    now = utcnow_naive()
    db.add(SupportMessage(ticket_id=t.id, author_user_id=user.id, body=body.body.strip(), created_at=now))
    t.status, t.updated_at, t.resolved_at = "open", now, None  # a reply puts it back with Zynora
    await db.commit()
    await alert_zynora(f"[THUTOra #{t.number}] School replied: {t.subject}", body.body.strip())
    return _summary(t, user)


@router.post("/tickets/{ticket_id}/resolve")
async def resolve(ticket_id: uuid.UUID, user: User = Depends(_support_user), db: AsyncSession = Depends(get_db)) -> dict:
    t = await _ticket_for(db, user, ticket_id)
    now = utcnow_naive()
    t.status, t.updated_at, t.resolved_at = "resolved", now, now
    await db.commit()
    return _summary(t, user)
