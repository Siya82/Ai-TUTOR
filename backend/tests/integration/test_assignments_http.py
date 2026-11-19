"""Answer review, mark override (#2) and changing assignments (#7)."""

from tests.integration.test_permissions import _test_assignment


async def test_teacher_sees_answers_and_overrides_mark(client, world, sessionmaker):
    aid = await _test_assignment(sessionmaker, world, released=True)
    lid = world.learners["a1"].id
    r = await client.get(f"/teach/assignments/{aid}/learners/{lid}/answers", headers=world.h("teacher_a"))
    assert r.status_code == 200
    data = r.json()
    assert data["can_mark"] and len(data["questions"]) == 3
    q = data["questions"][0]
    assert q["learner_response"] == "?" and q["is_correct"] is False and not q["marked_by_teacher"]

    before = (await client.get(f"/teach/assignments/{aid}", headers=world.h("teacher_a"))).json()
    marks_before = before["completions"][0]["marks_earned"]
    r = await client.post(f"/teach/assignments/{aid}/attempts/{q['attempt_id']}/mark", headers=world.h("teacher_a"),
                          json={"is_correct": True, "note": "Accepted: same thing written differently."})
    assert r.status_code == 200
    after = (await client.get(f"/teach/assignments/{aid}", headers=world.h("teacher_a"))).json()
    assert after["completions"][0]["marks_earned"] == marks_before + 1

    mine = (await client.get(f"/assignments/{aid}", headers=world.h("a1"))).json()
    first = next(x for x in mine["questions"] if x["id"] == q["question_id"])
    assert first["is_correct"] is True and first["marked_by_teacher"]
    assert first["teacher_note"].startswith("Accepted")

    # the audit trail recorded it
    events = (await client.get("/school/audit", headers=world.h("principal"))).json()
    assert any(e["action"] == "mark.override" for e in events["events"])


async def test_other_teacher_cannot_review_or_override(client, world, sessionmaker):
    aid = await _test_assignment(sessionmaker, world, released=True)
    lid = world.learners["a1"].id
    assert (await client.get(f"/teach/assignments/{aid}/learners/{lid}/answers",
                             headers=world.h("teacher_b"))).status_code == 404
    data = (await client.get(f"/teach/assignments/{aid}/learners/{lid}/answers", headers=world.h("teacher_a"))).json()
    att = data["questions"][0]["attempt_id"]
    r = await client.post(f"/teach/assignments/{aid}/attempts/{att}/mark", headers=world.h("teacher_b"),
                          json={"is_correct": True})
    assert r.status_code == 404


async def test_unreleased_override_stays_hidden_from_learner(client, world, sessionmaker):
    aid = await _test_assignment(sessionmaker, world, released=False)
    lid = world.learners["a1"].id
    data = (await client.get(f"/teach/assignments/{aid}/learners/{lid}/answers", headers=world.h("teacher_a"))).json()
    await client.post(f"/teach/assignments/{aid}/attempts/{data['questions'][0]['attempt_id']}/mark",
                      headers=world.h("teacher_a"), json={"is_correct": True, "note": "secret"})
    mine = (await client.get(f"/assignments/{aid}", headers=world.h("a1"))).json()
    assert all(x["teacher_note"] is None and x["is_correct"] is None for x in mine["questions"])


async def test_edit_close_duplicate_delete(client, world, sessionmaker):
    aid = await _test_assignment(sessionmaker, world, released=False)
    h = world.h("teacher_a")
    r = await client.patch(f"/teach/assignments/{aid}", headers=h,
                           json={"title": "Class test (moved)", "due_at": "2030-01-31T12:00:00+02:00"})
    assert r.status_code == 200 and r.json()["due_at"].startswith("2030-01-31T10:00")
    assert (await client.patch(f"/teach/assignments/{aid}", headers=world.h("teacher_b"),
                               json={"title": "x"})).status_code == 404

    assert (await client.post(f"/teach/assignments/{aid}/close", headers=h)).json()["closed"] is True
    qid = world.questions[0].id
    r = await client.post(f"/assignments/{aid}/questions/{qid}/answer", headers=world.h("a1"),
                          json={"learner_response": "2x"})
    assert r.status_code == 409

    # answered -> can't delete, but a duplicate can be deleted
    assert (await client.delete(f"/teach/assignments/{aid}", headers=h)).status_code == 409
    copy = (await client.post(f"/teach/assignments/{aid}/duplicate", headers=h)).json()
    detail = (await client.get(f"/teach/assignments/{copy['id']}", headers=h)).json()
    assert detail["title"].endswith("(copy)") and len(detail["questions"]) == 3 and not detail["closed"]
    assert (await client.delete(f"/teach/assignments/{copy['id']}", headers=h)).status_code == 204
    assert (await client.get(f"/teach/assignments/{copy['id']}", headers=h)).status_code == 404


async def test_question_report_hides_from_bank_when_resolved(client, world, sessionmaker):
    """deep scan M8."""
    from app.models import Question

    qid = world.questions[0].id
    r = await client.post(f"/teach/questions/{qid}/report", headers=world.h("teacher_a"),
                          json={"reason": "The model answer is wrong."})
    assert r.status_code == 201
    bank = (await client.get(f"/teach/questions?topic_id={world.topic.id}", headers=world.h("teacher_a"))).json()
    assert any(q["id"] == str(qid) for q in bank)
    async with sessionmaker() as db:  # what scripts/question_reports.py hide does
        (await db.get(Question, qid)).is_hidden = True
        await db.commit()
    bank = (await client.get(f"/teach/questions?topic_id={world.topic.id}", headers=world.h("teacher_a"))).json()
    assert all(q["id"] != str(qid) for q in bank)
