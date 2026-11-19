"""
NEW 20 Nov 2026 (deep scan M7). Real-HTTP tests for the routes that had
only unit tests on their pure parts: classes, roles and allocations;
notices; Today; dashboard scoping; insights; books; consent; parent SMS
sign-up; family viewer invites.
"""

from datetime import timedelta

from sqlalchemy import select

from app.core.clock import utcnow_naive

from app.models import LearnerGuardian, SignupCode, User
from app.services.family import new_otp

PASSWORD = "TestPass123!"


async def _login(client, school_id, number, password=PASSWORD):
    return await client.post(
        "/auth/login", json={"school_id": str(school_id), "student_number": number, "password": password}
    )


# --- classes, roles, allocations -----------------------------------------

async def test_only_management_shapes_the_school(client, world):
    r = await client.post("/school/classes", headers=world.h("teacher_a"), json={"name": "10C", "grade": 10})
    assert r.status_code == 403
    r = await client.post("/school/classes", headers=world.h("principal"), json={"name": "10C", "grade": 10})
    assert r.status_code == 200
    r = await client.post(
        f"/school/staff/{world.users['teacher_a'].id}/roles", headers=world.h("teacher_b"), json={"role": "principal"}
    )
    assert r.status_code == 403


async def test_allocation_grants_and_removal_revokes_access(client, world):
    def sees_a1(rows):
        return any(l["id"] == str(world.learners["a1"].id) for l in rows["learners"])

    progress = "/api/v1/dashboard/progress"
    assert not sees_a1((await client.get(progress, headers=world.h("teacher_b"))).json())

    r = await client.post(
        "/school/allocations",
        headers=world.h("principal"),
        json={
            "teacher_user_id": str(world.users["teacher_b"].id),
            "subject_id": str(world.subject.id),
            "class_id": str(world.classes["A"].id),
        },
    )
    assert r.status_code == 200
    assert sees_a1((await client.get(progress, headers=world.h("teacher_b"))).json())

    r = await client.delete(f"/school/allocations/{r.json()['id']}", headers=world.h("principal"))
    assert r.status_code == 204
    assert not sees_a1((await client.get(progress, headers=world.h("teacher_b"))).json())


# --- dashboard and Today ---------------------------------------------------

async def test_learner_detail_is_scoped(client, world):
    mine = await client.get(f"/api/v1/dashboard/learners/{world.learners['a1'].id}", headers=world.h("teacher_a"))
    assert mine.status_code == 200
    other = await client.get(f"/api/v1/dashboard/learners/{world.learners['b1'].id}", headers=world.h("teacher_a"))
    assert other.status_code in (403, 404)


async def test_today_counts_only_my_learners(client, world):
    r = await client.get("/teach/today", headers=world.h("teacher_a"))
    assert r.status_code == 200
    data = r.json()
    assert data["learner_count"] == 2  # a1 and a2, not b1
    assert data["quiet_count"] == 2
    assert (await client.get("/teach/today", headers=world.h("a1"))).status_code == 403


# --- notices -----------------------------------------------------------------

async def test_notice_reaches_parent_and_ack_is_recorded(client, world):
    r = await client.post("/school/notices", headers=world.h("a1"), json={"title": "x", "body": "y"})
    assert r.status_code == 403
    r = await client.post(
        "/school/notices",
        headers=world.h("principal"),
        json={"title": "Exam timetable", "body": "Papers start 3 June.", "grade": 10, "requires_ack": True},
    )
    assert r.status_code == 200
    notice_id = r.json()["id"]

    notices = (await client.get("/parent/notices", headers=world.h("parent"))).json()
    assert any(n["id"] == notice_id for n in notices)
    assert (await client.post(f"/parent/notices/{notice_id}/ack", headers=world.h("parent"))).status_code == 204


# --- insights and books ------------------------------------------------------

async def test_insights_is_for_officials_only(client, world):
    for who in ("teacher_a", "principal", "a1", "parent"):
        assert (await client.get("/insights/overview", headers=world.h(who))).status_code == 403


async def test_books_need_a_login(client, world):
    assert (await client.get("/books/")).status_code == 401
    r = await client.get("/books/", headers=world.h("a1"))
    assert r.status_code == 200 and isinstance(r.json(), list)


# --- consent -------------------------------------------------------------------

async def test_consent_recorded_by_own_teacher_only(client, world):
    a1 = world.learners["a1"].id
    body = {"given_by_name": "Thandi Mokoena", "relationship_to_learner": "Mother"}
    assert (await client.post(f"/school/learners/{a1}/consent", headers=world.h("teacher_b"), json=body)).status_code == 404
    r = await client.post(f"/school/learners/{a1}/consent", headers=world.h("teacher_a"), json=body)
    assert r.status_code == 200
    assert (await client.post(f"/school/learners/{a1}/consent/withdraw", headers=world.h("teacher_a"))).status_code == 204
    records = (await client.get(f"/school/learners/{a1}/consent", headers=world.h("teacher_a"))).json()
    assert records and all(c["withdrawn_at"] for c in records)


# --- parent sign-up by SMS code ----------------------------------------------

async def test_signup_verify_creates_parent_and_rejects_wrong_codes(client, world, sessionmaker):
    phone = "+27821234567"
    code, code_hash = new_otp()
    async with sessionmaker() as db:
        db.add(LearnerGuardian(learner_id=world.learners["a1"].id, full_name="Thandi Mokoena", cellphone=phone))
        db.add(SignupCode(school_id=world.school.id, cellphone=phone, code_hash=code_hash,
                          expires_at=utcnow_naive() + timedelta(minutes=10)))
        await db.commit()

    base = {"school_id": str(world.school.id), "cellphone": "082 123 4567", "password": "NewParent123!"}
    wrong = await client.post("/connect/signup/verify", json={**base, "code": "000000" if code != "000000" else "111111"})
    assert wrong.status_code == 400

    r = await client.post("/connect/signup/verify", json={**base, "code": code})
    assert r.status_code == 200, r.text
    login_number = r.json()["login_number"]
    assert (await _login(client, world.school.id, login_number, "NewParent123!")).status_code == 200

    again = await client.post("/connect/signup/verify", json={**base, "code": code})
    assert again.status_code == 400  # a code works once
    async with sessionmaker() as db:
        parent = (await db.execute(select(User).where(User.student_number == login_number,
                                                      User.school_id == world.school.id))).scalar_one()
        assert parent.role == "parent"


# --- family viewers (grandparent invites) -------------------------------------

async def test_viewer_invite_redeem_once(client, world):
    a1 = world.learners["a1"].id
    assert (await client.post(f"/parent/children/{world.learners['b1'].id}/viewers/invite",
                              headers=world.h("parent"), json={"viewer_name": "Gogo"})).status_code in (403, 404)
    r = await client.post(f"/parent/children/{a1}/viewers/invite", headers=world.h("parent"),
                          json={"viewer_name": "Gogo", "relationship": "Grandparent"})
    assert r.status_code == 200
    code = r.json()["code"]

    redeem = {"school_id": str(world.school.id), "code": code, "password": "GogoPass123!"}
    r = await client.post("/connect/viewer/redeem", json=redeem)
    assert r.status_code == 200, r.text
    assert (await _login(client, world.school.id, r.json()["login_number"], "GogoPass123!")).status_code == 200
    assert (await client.post("/connect/viewer/redeem", json=redeem)).status_code == 400
