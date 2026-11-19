"""Daily tutor limit (#3), conversation history (#5), token renewal (#5),
learner's own progress (#6), change password (#9)."""

import app.routers.tutor as tutor_router
from app.core.config import settings


async def _fake_ask(system_prompt, messages):
    return "Let's work through it: 3x."


async def test_daily_limit_and_history(client, world, monkeypatch):
    monkeypatch.setattr(tutor_router._tutor_client, "ask", _fake_ask)
    monkeypatch.setattr(settings, "tutor_daily_limit", 2)
    h = world.h("a1")
    body = {"message": "How do I simplify 2x + x?", "topic_id": str(world.topic.id)}
    r1 = await client.post("/tutor/message", headers=h, json=body)
    assert r1.status_code == 200, r1.text
    assert r1.json()["questions_left_today"] == 1
    assert (await client.post("/tutor/message", headers=h, json=body)).json()["questions_left_today"] == 0
    r3 = await client.post("/tutor/message", headers=h, json=body)
    assert r3.status_code == 429 and "tomorrow" in r3.json()["detail"]
    assert (await client.get("/tutor/usage", headers=h)).json() == {"used_today": 2, "limit": 2, "left_today": 0}

    sessions = (await client.get("/tutor/sessions", headers=h)).json()
    assert len(sessions) == 1 and sessions[0]["messages"] == 4
    msgs = (await client.get(f"/tutor/sessions/{sessions[0]['session_id']}/messages", headers=h)).json()["messages"]
    assert [m["role"] for m in msgs] == ["user", "assistant", "user", "assistant"]
    # another learner can't read it
    other = await client.get(f"/tutor/sessions/{sessions[0]['session_id']}/messages", headers=world.h("a2"))
    assert other.status_code == 404


async def test_refresh_token(client, world):
    r = await client.post("/auth/refresh", headers=world.h("teacher_a"))
    assert r.status_code == 200
    me = await client.get("/school/me", headers={"Authorization": f"Bearer {r.json()['access_token']}"})
    assert me.status_code == 200


async def test_change_own_password_any_role(client, world):
    for who in ("a1", "parent", "teacher_a"):
        user = world.users[who]
        r = await client.post("/auth/change-password", headers=world.h(who),
                              json={"current_password": "TestPass123!", "new_password": "NewPass456!"})
        assert r.status_code == 200, (who, r.text)
        ok = await client.post("/auth/login", json={"school_id": str(world.school.id),
                                                    "student_number": user.student_number,
                                                    "password": "NewPass456!"})
        assert ok.status_code == 200, who
        # the old token stops working (token_version bumped)
        assert (await client.post("/auth/refresh", headers=world.h(who))).status_code == 401


async def test_my_progress_matches_parent_view_and_hides_unreleased(client, world, sessionmaker):
    from tests.integration.test_permissions import _test_assignment

    await _test_assignment(sessionmaker, world, released=False)
    mine = (await client.get("/me/progress", headers=world.h("a1"))).json()
    assert mine["weakest_topics"] == [] and mine["grade"] == 10
    parents = (await client.get(f"/parent/children/{world.learners['a1'].id}/overview",
                                headers=world.h("parent"))).json()
    assert mine["week"] == parents["week"]
    assert (await client.get("/me/progress", headers=world.h("teacher_a"))).status_code in (401, 403, 404)
