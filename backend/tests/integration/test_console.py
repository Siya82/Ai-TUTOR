"""ADR-051: THUTOra Console -- sign-in, separation from school logins, roles,
and each Zynora action (with its audit line)."""

import uuid

from app.core.config import settings
from app.models import ConsoleStaff
from app.routers import console as console_module
from app.services import totp
from app.services.auth import hash_password
from tests.integration.conftest import auth

STAFF_PW = "ConsolePass123!"


async def make_staff(sessionmaker, role="agent", must_change=False, with_app=True) -> ConsoleStaff:
    async with sessionmaker() as db:
        s = ConsoleStaff(
            email=f"{role}-{uuid.uuid4().hex[:6]}@zynoratech.co.za",
            display_name=f"Test {role.title()}",
            role=role,
            password_hash=hash_password(STAFF_PW),
            must_change_password=must_change,
            totp_secret=totp.new_secret() if with_app else None,
            totp_confirmed=with_app,
        )
        db.add(s)
        await db.commit()
        return s


async def sign_in(client, staff: ConsoleStaff) -> dict:
    r = await client.post("/console/auth/login", json={"email": staff.email, "password": STAFF_PW})
    assert r.status_code == 200, r.text
    secret = r.json().get("secret") or staff.totp_secret
    mfa = {"Authorization": f"Bearer {r.json()['token']}"}
    r = await client.post("/console/auth/verify", headers=mfa, json={"code": totp.code_at(secret, totp.current_step())})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


async def test_school_logins_cannot_open_the_console(client, world):
    for who in ("principal", "admin", "teacher_a", "a1", "parent"):
        assert (await client.get("/console/me", headers=world.h(who))).status_code == 401
        assert (await client.get("/console/tickets", headers=world.h(who))).status_code == 401


async def test_console_logins_cannot_open_the_school_apps(client, sessionmaker):
    h = await sign_in(client, await make_staff(sessionmaker, "director"))
    assert (await client.get("/console/me", headers=h)).status_code == 200
    for path in ("/auth/me", "/school/me", "/support/tickets", "/school/audit"):
        assert (await client.get(path, headers=h)).status_code == 401, path


async def test_first_sign_in_sets_up_the_app_then_needs_a_new_password(client, sessionmaker):
    staff = await make_staff(sessionmaker, "agent", must_change=True, with_app=False)
    r = await client.post("/console/auth/login", json={"email": staff.email.upper(), "password": STAFF_PW})
    body = r.json()
    assert body["step"] == "setup" and body["otpauth_uri"].startswith("otpauth://totp/") and body["secret"]
    mfa = {"Authorization": f"Bearer {body['token']}"}
    # the half-way token opens nothing else
    assert (await client.get("/console/me", headers=mfa)).status_code == 401
    assert (await client.post("/console/auth/verify", headers=mfa, json={"code": "000000"})).status_code == 401
    code = totp.code_at(body["secret"], totp.current_step())
    r = await client.post("/console/auth/verify", headers=mfa, json={"code": code})
    assert r.status_code == 200 and r.json()["me"]["must_change_password"] is True
    h = {"Authorization": f"Bearer {r.json()['token']}"}
    assert (await client.get("/console/tickets", headers=h)).status_code == 403  # temp password first
    assert (await client.post("/console/auth/change-password", headers=h,
                              json={"current_password": STAFF_PW, "new_password": "short"})).status_code == 422
    r = await client.post("/console/auth/change-password", headers=h,
                          json={"current_password": STAFF_PW, "new_password": "A-much-better-one-42"})
    assert r.status_code == 200
    assert (await client.get("/console/me", headers=h)).status_code == 401  # old session ended
    h = {"Authorization": f"Bearer {r.json()['token']}"}
    assert (await client.get("/console/tickets", headers=h)).status_code == 200
    # the same code can't be used twice
    r = await client.post("/console/auth/login", json={"email": staff.email, "password": "A-much-better-one-42"})
    assert r.json()["step"] == "code"
    again = {"Authorization": f"Bearer {r.json()['token']}"}
    assert (await client.post("/console/auth/verify", headers=again, json={"code": code})).status_code == 401


async def test_wrong_passwords_are_throttled(client, sessionmaker):
    staff = await make_staff(sessionmaker)
    for _ in range(5):
        r = await client.post("/console/auth/login", json={"email": staff.email, "password": "nope"})
        assert r.status_code == 401
    r = await client.post("/console/auth/login", json={"email": staff.email, "password": STAFF_PW})
    assert r.status_code == 429


async def test_what_each_console_role_can_open(client, sessionmaker):
    paths = {"/console/tickets": "agent", "/console/schools": "agent", "/console/registrations": "lead",
             "/console/insights": "lead", "/console/audit": "lead", "/console/staff": "director"}
    rank = {"agent": 0, "lead": 1, "director": 2}
    for role in ("agent", "lead", "director"):
        h = await sign_in(client, await make_staff(sessionmaker, role))
        for path, needs in paths.items():
            want = 200 if rank[role] >= rank[needs] else 403
            assert (await client.get(path, headers=h)).status_code == want, (role, path)


async def test_ticket_reply_reaches_the_school_and_is_logged(client, world, sessionmaker):
    t = (await client.post("/support/tickets", headers=world.h("teacher_a"), json={
        "product": "teach", "category": "how_to", "subject": "Where is release?", "body": "Can't find it."})).json()
    agent = await make_staff(sessionmaker, "agent")
    h = await sign_in(client, agent)
    listed = (await client.get("/console/tickets?view=open", headers=h)).json()["tickets"]
    assert t["number"] in [x["number"] for x in listed]
    detail = (await client.get(f"/console/tickets/{t['number']}", headers=h)).json()
    assert detail["from"]["name"] == "Teacher A" and detail["messages"][0]["body"] == "Can't find it."
    r = await client.post(f"/console/tickets/{t['number']}/reply", headers=h, json={"body": "Open the test, then Release."})
    assert r.status_code == 200 and r.json()["status"] == "waiting_on_school"
    assert r.json()["messages"][-1]["author"] == "Test Agent"
    seen = (await client.get(f"/support/tickets/{t['id']}", headers=world.h("teacher_a"))).json()
    assert seen["messages"][-1]["body"] == "Open the test, then Release."
    # the school's Activity shows THUTOra support, not the person's name
    events = (await client.get("/school/audit", headers=world.h("principal"))).json()["events"]
    assert any(e["by"] == "THUTOra support" and e["action"] == "ticket.reply" for e in events)
    r = await client.post(f"/console/tickets/{t['number']}/update", headers=h, json={"priority": "p2"})
    assert r.json()["priority"] == "p2"
    lead = await sign_in(client, await make_staff(sessionmaker, "lead"))
    log = (await client.get("/console/audit", headers=lead)).json()["events"]
    assert any(e["by"] == "Test Agent" and e["action"] == "ticket.reply" for e in log)


async def test_school_lookup_never_shows_learners(client, world, sessionmaker):
    h = await sign_in(client, await make_staff(sessionmaker, "agent"))
    found = (await client.get(f"/console/schools?q={world.school.name}", headers=h)).json()["schools"]
    assert [s["learners"] for s in found] == [3]
    detail = (await client.get(f"/console/schools/{world.school.id}", headers=h)).text
    assert "Principal" in detail
    for name in ("a1", "a2", "b1"):
        assert world.users[name].student_number not in detail
    assert "Learner A1" not in detail


async def test_no_console_route_touches_learner_work_or_conversations():
    paths = " ".join(r.path for r in console_module.router.routes).lower()
    for word in ("learner", "conversation", "tutor", "attempt", "mark", "assignment", "progress"):
        assert word not in paths
    source = open(console_module.__file__).read()
    for model in ("TutorMessage", "TutorSession", "Attempt", "Learner,", "AssignmentTarget"):
        assert model not in source


async def test_registration_is_approved_from_the_console(client, sessionmaker):
    reg = (await client.post("/schools/registrations", json={
        "school_name": f"Console High {uuid.uuid4().hex[:5]}", "province": "KwaZulu-Natal", "contact_name": "Ms P. Zulu",
        "contact_role": "Principal", "contact_cellphone": "072 111 2233", "emis_number": "500111222"})).json()
    h = await sign_in(client, await make_staff(sessionmaker, "lead"))
    regs = (await client.get("/console/registrations", headers=h)).json()["registrations"]
    mine = next(r for r in regs if r["reference"] == reg["reference"])
    r = await client.post(f"/console/registrations/{mine['id']}/approve", headers=h, json={"as_role": "principal"})
    assert r.status_code == 200, r.text
    cred = r.json()["credentials"]
    assert cred["temp_password"] and cred["name"] == "Ms P. Zulu"
    school_id = r.json()["registration"]["school_id"]
    login = await client.post("/auth/login", json={"school_id": school_id, "student_number": cred["login"],
                                                   "password": cred["temp_password"]})
    assert login.status_code == 200 and login.json()["must_change_password"] is True
    assert (await client.post(f"/console/registrations/{mine['id']}/approve", headers=h, json={})).status_code == 400


async def test_principal_handover(client, world, sessionmaker):
    h = await sign_in(client, await make_staff(sessionmaker, "lead"))
    sid = world.school.id
    r = await client.post(f"/console/schools/{sid}/principal", headers=h,
                          json={"existing_user_id": str(world.users["teacher_a"].id)})
    assert r.status_code == 200 and r.json()["credentials"] is None
    team = (await client.get(f"/console/schools/{sid}", headers=h)).json()["team"]
    old = next(t for t in team if t["role"] == "principal" and t["user_id"] == str(world.users["principal"].id))
    admin_role = next(t for t in team if t["role"] == "school_admin")
    # the school manages its other roles itself
    assert (await client.post(f"/console/schools/{sid}/roles/{admin_role['role_id']}/remove", headers=h,
                              json={})).status_code == 400
    r = await client.post(f"/console/schools/{sid}/roles/{old['role_id']}/remove", headers=h, json={"switch_off": True})
    assert r.status_code == 200 and r.json()["principals_left"] == 1
    assert (await client.get("/school/me", headers=world.h("principal"))).status_code == 401
    me = (await client.get("/school/me", headers=world.h("teacher_a"))).json()
    assert "principal" in [x["role"] for x in me["roles"]]
    # a brand-new principal login
    r = await client.post(f"/console/schools/{sid}/principal", headers=h, json={"display_name": "Mr New Head"})
    assert r.json()["credentials"]["temp_password"]


async def test_officials_are_added_and_removed(client, world, sessionmaker):
    h = await sign_in(client, await make_staff(sessionmaker, "lead"))
    tag = uuid.uuid4().hex[:5]
    d = (await client.post("/console/districts", headers=h, json={"name": f"Dist {tag}", "province": "KwaZulu-Natal"})).json()
    c = (await client.post("/console/circuits", headers=h, json={"district_id": d["id"], "name": f"Circ {tag}"})).json()
    assert (await client.post(f"/console/schools/{world.school.id}/circuit", headers=h,
                              json={"circuit_id": c["id"]})).status_code == 200
    r = await client.post("/console/officials", headers=h, json={"name": "Mr T. Official", "circuit_id": c["id"]})
    assert r.status_code == 201 and r.json()["credentials"]["school"] == f"Circ {tag} Circuit Office"
    tree = (await client.get("/console/insights", headers=h)).json()
    circ = next(x for dd in tree["districts"] for x in dd["circuits"] if x["id"] == c["id"])
    assert [o["name"] for o in circ["officials"]] == ["Mr T. Official"] and circ["schools"][0]["name"] == world.school.name
    uid = circ["officials"][0]["user_id"]
    async with sessionmaker() as db:
        from app.models import User

        official = await db.get(User, uuid.UUID(uid))
    headers = auth(official)
    assert (await client.post(f"/console/officials/{uid}/remove", headers=h)).status_code == 200
    assert (await client.get("/insights/overview", headers=headers)).status_code == 401
    assert (await client.post("/console/officials", headers=h, json={"name": "X Y"})).status_code == 400


async def test_directors_manage_console_staff(client, sessionmaker):
    director = await make_staff(sessionmaker, "director")
    h = await sign_in(client, director)
    r = await client.post("/console/staff", headers=h, json={"email": f"new-{uuid.uuid4().hex[:5]}@zynoratech.co.za",
                                                            "display_name": "New Agent", "role": "agent"})
    assert r.status_code == 201 and len(r.json()["temp_password"]) >= 14
    new_id = r.json()["staff"]["id"]
    assert (await client.post(f"/console/staff/{new_id}", headers=h, json={"role": "lead"})).json()["staff"]["role"] == "lead"
    assert (await client.post(f"/console/staff/{director.id}", headers=h, json={"role": "agent"})).status_code == 400
    r = await client.post(f"/console/staff/{new_id}/reset-authenticator", headers=h)
    assert r.json()["staff"]["authenticator_set_up"] is False
    assert (await client.post(f"/console/staff/{new_id}", headers=h, json={"active": False})).json()["staff"]["active"] is False


async def test_school_app_address_is_refused(client, sessionmaker, monkeypatch):
    h = await sign_in(client, await make_staff(sessionmaker, "agent"))
    school_origin = settings.cors_origins[0]
    r = await client.get("/console/tickets", headers={**h, "Origin": school_origin})
    assert r.status_code == 403
    ok = await client.get("/console/tickets", headers={**h, "Origin": settings.console_origins[0]})
    assert ok.status_code == 200
    monkeypatch.setattr(settings, "console_enabled", False)
    assert (await client.get("/console/tickets", headers=h)).status_code == 404


async def test_console_actions_show_in_school_activity(client, world, sessionmaker):
    h = await sign_in(client, await make_staff(sessionmaker, "lead"))
    await client.post(f"/console/schools/{world.school.id}/principal", headers=h,
                      json={"existing_user_id": str(world.users["teacher_b"].id)})
    events = (await client.get("/school/audit", headers=world.h("principal"))).json()["events"]
    added = [e for e in events if e["action"] == "principal.add"]
    assert added and added[0]["by"] == "THUTOra support" and added[0]["label"] == "Added a principal"
