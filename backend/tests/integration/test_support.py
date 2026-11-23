"""ADR-050: support tickets -- who can log and see them, and the reply loop."""

import uuid

from sqlalchemy import select

from app.models import School, SupportTicket, User
from app.services.support import priority_for, whatsapp_link
from tests.integration.conftest import auth

NEW = {"product": "teach", "category": "how_to", "subject": "How do I release results?",
       "body": "I set a test and can't find the button.", "screen": "assignments"}


async def test_contact_is_public(client):
    r = await client.get("/support/contact")
    assert r.status_code == 200
    data = r.json()
    assert data["email"] and data["whatsapp_link"].startswith("https://wa.me/27")
    assert any(c["id"] == "safeguarding" and c["urgent"] for c in data["categories"])


async def test_learners_and_parents_are_sent_to_their_school(client, world):
    for who in ("a1", "parent"):
        r = await client.post("/support/tickets", headers=world.h(who), json=NEW)
        assert r.status_code == 403 and "school" in r.json()["detail"]


async def test_teacher_logs_a_ticket_and_sees_only_their_own(client, world):
    r = await client.post("/support/tickets", headers=world.h("teacher_a"), json=NEW)
    assert r.status_code == 201
    t = r.json()
    assert t["priority"] == "p3" and t["status"] == "open" and t["number"] > 0
    other = await client.post("/support/tickets", headers=world.h("teacher_b"), json={**NEW, "subject": "Mine"})
    mine = (await client.get("/support/tickets", headers=world.h("teacher_a"))).json()
    assert [x["id"] for x in mine] == [t["id"]]  # not teacher_b's
    assert (await client.get(f"/support/tickets/{other.json()['id']}", headers=world.h("teacher_a"))).status_code == 404
    # the principal manages the school: sees both
    everything = (await client.get("/support/tickets", headers=world.h("principal"))).json()
    assert {t["id"], other.json()["id"]} <= {x["id"] for x in everything}


async def test_another_school_cannot_see_a_ticket(client, world, sessionmaker):
    t = (await client.post("/support/tickets", headers=world.h("teacher_a"), json=NEW)).json()
    async with sessionmaker() as db:
        school = School(name=f"Other {uuid.uuid4().hex[:6]}")
        db.add(school)
        await db.flush()
        u = User(role="teacher", school_id=school.id, student_number="TX1", password_hash="x")
        db.add(u)
        await db.commit()
        headers = auth(u)
    assert (await client.get(f"/support/tickets/{t['id']}", headers=headers)).status_code == 404


async def test_reply_loop_and_resolve(client, world, sessionmaker):
    import scripts.support as support_script

    t = (await client.post("/support/tickets", headers=world.h("teacher_a"), json=NEW)).json()
    support_script.async_session_factory = sessionmaker
    await support_script.reply(t["number"], "Click 'Release results to students' on the test.", resolve=False)
    detail = (await client.get(f"/support/tickets/{t['id']}", headers=world.h("teacher_a"))).json()
    assert detail["status"] == "waiting_on_school"
    assert [m["from_zynora"] for m in detail["messages"]] == [False, True]
    r = await client.post(f"/support/tickets/{t['id']}/messages", headers=world.h("teacher_a"), json={"body": "Found it, thanks"})
    assert r.json()["status"] == "open"  # back with Zynora
    r = await client.post(f"/support/tickets/{t['id']}/resolve", headers=world.h("teacher_a"))
    assert r.json()["status"] == "resolved"


async def test_urgent_categories_and_daily_limit(client, world, sessionmaker):
    r = await client.post("/support/tickets", headers=world.h("teacher_a"),
                          json={**NEW, "category": "safeguarding", "subject": "Worried about a learner"})
    assert r.json()["priority"] == "p1"
    assert priority_for("bug", blocking=True) == "p2" and priority_for("idea", blocking=False) == "p4"
    codes = [(await client.post("/support/tickets", headers=world.h("teacher_b"), json=NEW)).status_code for _ in range(11)]
    assert codes[:10] == [201] * 10 and codes[10] == 429
    async with sessionmaker() as db:
        assert (await db.execute(select(SupportTicket).where(SupportTicket.category == "nope"))).first() is None
    assert (await client.post("/support/tickets", headers=world.h("teacher_a"), json={**NEW, "category": "nope"})).status_code == 422


def test_whatsapp_link_formats():
    assert whatsapp_link("067 590 1165") == "https://wa.me/27675901165"
    assert whatsapp_link("+27 67 590 1165") == "https://wa.me/27675901165"
