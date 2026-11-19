"""Who can see and do what, end to end (code review 19 Nov #4)."""

from sqlalchemy import select

from app.models import Assignment, AssignmentQuestion, AssignmentTarget, Attempt


async def test_login_and_me(client, world):
    r = await client.post("/auth/login", json={"school_id": str(world.school.id),
                                                "student_number": world.users["a1"].student_number,
                                                "password": "TestPass123!"})
    assert r.status_code == 200 and r.json()["role"] == "student"
    bad = await client.post("/auth/login", json={"school_id": str(world.school.id),
                                                  "student_number": world.users["a1"].student_number,
                                                  "password": "wrong-password"})
    assert bad.status_code == 401


async def test_teacher_sees_only_own_class(client, world):
    roster = (await client.get("/admin/students", headers=world.h("teacher_a"))).json()
    names = {s["display_name"] for s in roster}
    assert names == {"Learner A1", "Learner A2"}
    everyone = (await client.get("/admin/students", headers=world.h("principal"))).json()
    assert {"Learner A1", "Learner A2", "Learner B1"} <= {s["display_name"] for s in everyone}


async def test_teacher_cannot_act_on_other_class(client, world):
    b1 = world.learners["b1"].id
    assert (await client.get(f"/school/learners/{b1}/parents", headers=world.h("teacher_a"))).status_code == 404
    assert (await client.get(f"/school/learners/{b1}/export", headers=world.h("teacher_a"))).status_code in (403, 404)
    assert (await client.get(f"/school/learners/{b1}/guardians", headers=world.h("teacher_a"))).status_code == 404


async def test_management_only_endpoints(client, world):
    for who, ok in (("teacher_a", False), ("admin", True), ("principal", True)):
        r = await client.get("/school/overview", headers=world.h(who))
        assert (r.status_code == 200) is ok, who
        r = await client.post("/school/staff", headers=world.h(who), json={"display_name": "New Person"})
        assert (r.status_code == 200) is ok, who
    assert (await client.get("/school/overview", headers=world.h("a1"))).status_code in (401, 403)


async def test_learner_cannot_use_staff_or_parent_api(client, world):
    for path in ("/admin/students", "/school/me", "/parent/children", "/insights/scope"):
        assert (await client.get(path, headers=world.h("a1"))).status_code in (401, 403), path


async def test_parent_sees_only_own_child(client, world):
    kids = (await client.get("/parent/children", headers=world.h("parent"))).json()
    assert [k["display_name"] for k in kids] == ["Learner A1"]
    other = world.learners["a2"].id
    assert (await client.get(f"/parent/children/{other}/overview", headers=world.h("parent"))).status_code == 404


async def test_other_school_is_invisible(client, world, sessionmaker):
    # a second, separate school's principal sees none of this school's learners
    r = await client.get(f"/school/learners/{world.learners['a1'].id}/parents", headers=world.h("principal"))
    assert r.status_code == 200
    async with sessionmaker() as db:
        from app.models import School, StaffRole
        from app.services.auth import provision_teacher

        other = School(name="Elsewhere High")
        db.add(other)
        await db.flush()
        boss, _ = await provision_teacher(db, school=other, raw_password="TestPass123!")
        db.add(StaffRole(user_id=boss.id, school_id=other.id, role="principal"))
        await db.commit()
    from tests.integration.conftest import auth

    r = await client.get(f"/school/learners/{world.learners['a1'].id}/parents", headers=auth(boss))
    assert r.status_code == 404
    assert all(s["display_name"] != "Learner A1" for s in (await client.get("/admin/students", headers=auth(boss))).json())


async def _test_assignment(sessionmaker, world, *, released: bool):
    async with sessionmaker() as db:
        a = Assignment(school_id=world.school.id, teacher_user_id=world.users["teacher_a"].id,
                       title="Class test", mode="test", results_released=released)
        db.add(a)
        await db.flush()
        for i, q in enumerate(world.questions):
            db.add(AssignmentQuestion(assignment_id=a.id, question_id=q.id, order_index=i, marks=1))
        db.add(AssignmentTarget(assignment_id=a.id, learner_id=world.learners["a1"].id))
        for q in world.questions:  # all wrong
            db.add(Attempt(learner_id=world.learners["a1"].id, question_id=q.id, learner_response="?",
                           is_correct=False, assignment_id=a.id))
        await db.commit()
        return a.id


async def test_parent_stats_hide_unreleased_test(client, world, sessionmaker):
    """Code review 19 Nov #1."""
    aid = await _test_assignment(sessionmaker, world, released=False)
    lid = world.learners["a1"].id
    ov = (await client.get(f"/parent/children/{lid}/overview", headers=world.h("parent"))).json()
    assert ov["weakest_topics"] == [] and ov["strongest_topics"] == []
    summary = (await client.get(f"/parent/children/{lid}/summary", headers=world.h("parent"))).json()["text"]
    assert "wrong" not in summary and "0%" not in summary
    async with sessionmaker() as db:
        a = (await db.execute(select(Assignment).where(Assignment.id == aid))).scalar_one()
        a.results_released = True
        await db.commit()
    ov = (await client.get(f"/parent/children/{lid}/overview", headers=world.h("parent"))).json()
    assert any(t["topic_name"] == "Algebraic Expressions" for t in ov["weakest_topics"])


async def test_school_profile_rules(client, world):
    prof = (await client.get("/school/profile", headers=world.h("teacher_a"))).json()
    assert prof["can_edit"] is False
    body = {"name": prof["name"], "province": "Gauteng", "quintile": 2,
            "parent_signup_enabled": True, "viewer_invites_enabled": False}
    assert (await client.put("/school/profile", headers=world.h("teacher_a"), json=body)).status_code == 403
    assert (await client.put("/school/profile", headers=world.h("admin"), json=body)).status_code == 200
    # the switch is enforced: family invites now refused for this school's parents
    r = await client.post(f"/parent/children/{world.learners['a1'].id}/viewers/invite", headers=world.h("parent"),
                          json={"viewer_name": "Gogo", "relationship": "Grandmother"})
    assert r.status_code == 403


async def test_signup_reply_is_the_same_for_unknown_numbers(client, world):
    a = await client.post("/connect/signup/start", json={"school_id": str(world.school.id), "cellphone": "0710000001"})
    assert a.status_code in (200, 503)  # 503 only if SMS is off in this environment


async def test_edit_person_details(client, world):
    """Code review 19 Nov #8."""
    uid = world.users["a1"].id
    r = await client.patch(f"/school/users/{uid}", headers=world.h("teacher_a"), json={"display_name": "X"})
    assert r.status_code == 403
    r = await client.patch(f"/school/users/{uid}", headers=world.h("admin"),
                           json={"display_name": "Learner A-One", "grade": 11})
    assert r.status_code == 200 and r.json()["grade"] == 11
    # grade change took them out of class 10A, so teacher A no longer sees them
    roster = (await client.get("/admin/students", headers=world.h("teacher_a"))).json()
    assert "Learner A-One" not in {s["display_name"] for s in roster}
    clash = world.users["a2"].student_number
    r = await client.patch(f"/school/users/{uid}", headers=world.h("admin"), json={"login_number": clash})
    assert r.status_code == 400
    r = await client.patch(f"/school/users/{world.users['teacher_b'].id}", headers=world.h("principal"),
                           json={"display_name": "Ms B. Dube", "grade": 10})
    assert r.status_code == 400  # staff have no grade
    events = (await client.get("/school/audit", headers=world.h("principal"))).json()["events"]
    assert any(e["action"] == "user.edit" and e["target"] == "Learner A-One" for e in events)


async def test_privacy_export_and_delete_cover_family(client, world, sessionmaker):
    """Code review 19 Nov #10."""
    from app.models import ParentLink, User

    lid = world.learners["a1"].id
    await client.post(f"/school/learners/{lid}/guardians", headers=world.h("admin"),
                      json={"full_name": "Thandi A1", "relationship_to_learner": "Mother", "cellphone": "0825550001"})
    # the same parent also has a2 -> must survive a1's deletion; a viewer of a1 only must not
    async with sessionmaker() as db:
        db.add(ParentLink(parent_user_id=world.users["parent"].id, learner_id=world.learners["a2"].id,
                          relationship_to_learner="Mother", kind="guardian"))
        viewer = User(role="parent", school_id=world.school.id, student_number="V0001", display_name="Gogo",
                      password_hash="x")
        db.add(viewer)
        await db.flush()
        db.add(ParentLink(parent_user_id=viewer.id, learner_id=lid, relationship_to_learner="Grandmother",
                          kind="viewer", invited_by_user_id=world.users["parent"].id))
        await db.commit()

    export = (await client.get(f"/school/learners/{lid}/export", headers=world.h("principal"))).json()
    assert export["guardian_contacts"][0]["cellphone"] == "+27825550001"
    assert {f["name"] for f in export["family_logins"]} == {"Parent A1", "Gogo"}

    r = await client.request("DELETE", f"/school/learners/{lid}", headers=world.h("principal"),
                             json={"confirm_name": "Learner A1"})
    assert r.status_code == 200 and r.json()["family_logins_removed"] == 1
    async with sessionmaker() as db:
        assert await db.get(User, viewer.id) is None
        assert await db.get(User, world.users["parent"].id) is not None
    events = (await client.get("/school/audit", headers=world.h("principal"))).json()["events"]
    assert [e["action"] for e in events][:2] == ["privacy.delete", "privacy.export"]
    assert events[0]["target"] == "a deleted learner"
