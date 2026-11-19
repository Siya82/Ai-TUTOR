"""deep scan H5 (usage + budget), M1 (consent switch)."""

import app.routers.tutor as tutor_router
from app.services.ai_cost import cost_usd


async def _fake_ask(system, messages, max_tokens=None, on_usage=None):
    if on_usage:
        on_usage({"model": "claude-sonnet-4-6", "input_tokens": 3000, "output_tokens": 500,
                  "cache_read_tokens": 1200, "cache_write_tokens": 0})
    return "A hint."


def test_cost_formula():
    assert round(cost_usd("claude-sonnet-4-6", 1_000_000, 0), 2) == 3.0
    assert round(cost_usd("claude-sonnet-4-6", 0, 1_000_000), 2) == 15.0
    assert round(cost_usd("unknown-model", 1_000_000, 0), 2) == 3.0  # priced like Sonnet


async def _settings(client, world, **changes):
    prof = (await client.get("/school/profile", headers=world.h("principal"))).json()
    body = {k: prof[k] for k in ("name", "emis_number", "province", "quintile", "phone", "email", "physical_address",
                                 "parent_signup_enabled", "viewer_invites_enabled", "require_consent",
                                 "ai_budget_usd_month")}
    body.update(changes)
    r = await client.put("/school/profile", headers=world.h("principal"), json=body)
    assert r.status_code == 200, r.text


async def test_usage_is_recorded_and_budget_pauses_ai(client, world, monkeypatch):
    monkeypatch.setattr(tutor_router._tutor_client, "ask", _fake_ask)
    q = {"message": "help", "topic_id": str(world.topic.id)}
    assert (await client.post("/tutor/message", headers=world.h("a1"), json=q)).status_code == 200
    usage = (await client.get("/school/ai-usage", headers=world.h("principal"))).json()
    expected = cost_usd("claude-sonnet-4-6", 3000, 500, 1200, 0)
    assert usage["by_feature"]["tutor"]["calls"] == 1 and abs(usage["cost_usd"] - round(expected, 4)) < 1e-6
    assert (await client.get("/school/ai-usage", headers=world.h("teacher_a"))).status_code == 403

    await _settings(client, world, ai_budget_usd_month=0.01)  # already spent ~$0.017
    r = await client.post("/tutor/message", headers=world.h("a1"), json=q)
    assert r.status_code == 429 and "allowance" in r.json()["detail"]


async def test_consent_switch(client, world, monkeypatch):
    monkeypatch.setattr(tutor_router._tutor_client, "ask", _fake_ask)
    q = {"message": "help", "topic_id": str(world.topic.id)}
    await _settings(client, world, require_consent=True)
    r = await client.post("/tutor/message", headers=world.h("a1"), json=q)
    assert r.status_code == 403 and "consent" in r.json()["detail"]
    lid = world.learners["a1"].id
    rec = await client.post(f"/school/learners/{lid}/consent", headers=world.h("teacher_a"),
                            json={"given_by_name": "Thandi", "relationship_to_learner": "Mother", "method": "signed_form"})
    assert rec.status_code == 200, rec.text
    assert (await client.post("/tutor/message", headers=world.h("a1"), json=q)).status_code == 200


async def test_open_test_question_gets_coaching_only(client, world, sessionmaker, monkeypatch):
    """deep scan M5."""
    from tests.integration.test_permissions import _test_assignment

    seen = {}

    async def spy(system, messages, max_tokens=None, on_usage=None):
        seen["system"] = system
        return "Looks like a test question -- let's try a different example."

    monkeypatch.setattr(tutor_router._tutor_client, "ask", spy)
    aid = await _test_assignment(sessionmaker, world, released=False)
    q = world.questions[1].text
    assert (await client.post("/tutor/message", headers=world.h("a1"),
                              json={"message": f"how do I do this: {q}", "topic_id": str(world.topic.id)})).status_code == 200
    assert "TEST IN PROGRESS" in seen["system"]
    # an unrelated question gets normal help
    await client.post("/tutor/message", headers=world.h("a1"),
                      json={"message": "what is a like term?", "topic_id": str(world.topic.id)})
    assert "TEST IN PROGRESS" not in seen["system"]
    review = (await client.get(f"/teach/assignments/{aid}/learners/{world.learners['a1'].id}/answers",
                               headers=world.h("teacher_a"))).json()
    assert review["tutor_asked_during_test"] == 1
