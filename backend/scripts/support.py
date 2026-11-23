"""
NEW 23 Nov 2026 (ADR-050). Zynora's side of THUTOra support. Run from backend/:

    python -m scripts.support list            # waiting for Zynora (open), most urgent first
    python -m scripts.support list --all      # every ticket that isn't resolved
    python -m scripts.support show 42         # one ticket and its conversation
    python -m scripts.support reply 42 "Thanks -- fixed, please refresh."            # -> waiting on school
    python -m scripts.support reply 42 "All sorted." --resolve                        # -> resolved
    python -m scripts.support priority 42 p2  # change priority (p1 urgent .. p4 idea)

Statuses: open (Zynora's turn), waiting_on_school (the school's turn), resolved.
The school sees replies in the Help Centre under "My tickets".
"""

import argparse
import asyncio

from sqlalchemy import case, select

from app.core.clock import utcnow_naive
from app.core.database import async_session_factory
from app.models import School, SupportMessage, SupportTicket, User
from app.services.support import CATEGORIES, PRIORITY_LABEL

ORDER = case({"p1": 1, "p2": 2, "p3": 3, "p4": 4}, value=SupportTicket.priority, else_=5)


async def _get(db, number: int) -> SupportTicket:
    t = (await db.execute(select(SupportTicket).where(SupportTicket.number == number))).scalar_one_or_none()
    if t is None:
        raise SystemExit(f"No ticket {number}.")
    return t


async def list_tickets(show_all: bool) -> None:
    async with async_session_factory() as db:
        q = select(SupportTicket, School.name).join(School, School.id == SupportTicket.school_id)
        q = q.where(SupportTicket.status != "resolved") if show_all else q.where(SupportTicket.status == "open")
        rows = (await db.execute(q.order_by(ORDER, SupportTicket.created_at))).all()
    if not rows:
        print("Nothing waiting." if not show_all else "No unresolved tickets.")
    for t, school in rows:
        age = utcnow_naive() - t.created_at
        hours = int(age.total_seconds() // 3600)
        print(f"#{t.number:<5} {PRIORITY_LABEL[t.priority]:<20} {t.status:<18} {hours:>4}h  {school[:30]:<30} {t.subject}")


async def show(number: int) -> None:
    async with async_session_factory() as db:
        t = await _get(db, number)
        school = await db.get(School, t.school_id)
        creator = await db.get(User, t.created_by_user_id)
        msgs = (
            await db.execute(select(SupportMessage).where(SupportMessage.ticket_id == t.id).order_by(SupportMessage.created_at))
        ).scalars().all()
    print(f"#{t.number}  {t.subject}")
    print(f"  {PRIORITY_LABEL[t.priority]} · {CATEGORIES.get(t.category, (t.category,))[0]} · {t.status}")
    print(f"  {school.name if school else '?'} · from {creator.student_number if creator else '?'} ({t.product})")
    print(f"  context: {t.context}")
    for m in msgs:
        who = "ZYNORA" if m.from_zynora else "SCHOOL"
        print(f"\n  [{m.created_at:%Y-%m-%d %H:%M}] {who}\n  " + m.body.replace("\n", "\n  "))


async def reply(number: int, text: str, resolve: bool) -> None:
    async with async_session_factory() as db:
        t = await _get(db, number)
        now = utcnow_naive()
        db.add(SupportMessage(ticket_id=t.id, from_zynora=True, body=text.strip(), created_at=now))
        t.status = "resolved" if resolve else "waiting_on_school"
        t.updated_at = now
        t.resolved_at = now if resolve else None
        await db.commit()
    print(f"#{number}: reply saved; now {t.status}. The school sees it in the Help Centre.")


async def set_priority(number: int, priority: str) -> None:
    async with async_session_factory() as db:
        t = await _get(db, number)
        t.priority = priority
        await db.commit()
    print(f"#{number}: priority {PRIORITY_LABEL[priority]}.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("list")
    p.add_argument("--all", action="store_true")
    p = sub.add_parser("show")
    p.add_argument("number", type=int)
    p = sub.add_parser("reply")
    p.add_argument("number", type=int)
    p.add_argument("text")
    p.add_argument("--resolve", action="store_true")
    p = sub.add_parser("priority")
    p.add_argument("number", type=int)
    p.add_argument("priority", choices=list(PRIORITY_LABEL))
    a = ap.parse_args()
    if a.cmd == "list":
        asyncio.run(list_tickets(a.all))
    elif a.cmd == "show":
        asyncio.run(show(a.number))
    elif a.cmd == "reply":
        asyncio.run(reply(a.number, a.text, a.resolve))
    else:
        asyncio.run(set_priority(a.number, a.priority))
