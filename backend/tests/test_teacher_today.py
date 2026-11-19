"""ADR-036: the teacher's Today panel (pure rules)."""

import uuid
from datetime import datetime, timedelta

from app.services.teacher_today import (
    Answer,
    TopicInfo,
    make_practice_question_ids,
    summarise_today,
)

NOW = datetime(2026, 11, 19, 7, 0)
A, B, C = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
LEARNERS = {A: "Amahle", B: "Bongani", C: "Chloe"}
T1, T2 = uuid.uuid4(), uuid.uuid4()
TOPICS = {
    T1: TopicInfo(T1, "Factorisation", "Pure Mathematics", 10),
    T2: TopicInfo(T2, "Exponents", "Pure Mathematics", 10),
}


def ans(lid, tid, ok, days_ago=1):
    return Answer(lid, uuid.uuid4(), tid, ok, NOW - timedelta(days=days_ago))


def test_needs_help_requires_repeated_mostly_wrong_answers():
    answers = [
        ans(A, T1, False), ans(A, T1, False), ans(A, T1, True),   # 2 of 3 wrong -> help
        ans(B, T1, False), ans(B, T1, True), ans(B, T1, True),    # 1 wrong -> fine
    ]
    out = summarise_today(LEARNERS, answers, TOPICS, NOW)
    assert [h["learner_name"] for h in out["needs_help"]] == ["Amahle"]
    assert out["needs_help"][0]["wrong"] == 2


def test_old_answers_are_ignored():
    answers = [ans(A, T1, False, days_ago=10), ans(A, T1, False, days_ago=9)]
    out = summarise_today(LEARNERS, answers, TOPICS, NOW)
    assert out["needs_help"] == []
    assert out["active_count"] == 0


def test_weak_topics_sorted_by_accuracy_and_list_strugglers():
    answers = [
        ans(A, T1, False), ans(B, T1, False), ans(C, T1, True),   # 33%
        ans(A, T2, True), ans(B, T2, False),                     # 50%
    ]
    out = summarise_today(LEARNERS, answers, TOPICS, NOW)
    assert [w["topic_name"] for w in out["weak_topics"]] == ["Factorisation", "Exponents"]
    assert set(out["weak_topics"][0]["learner_ids"]) == {str(A), str(B)}
    assert out["weak_topics"][0]["accuracy"] == 33


def test_quiet_learners_are_those_with_no_recent_answers():
    out = summarise_today(LEARNERS, [ans(A, T1, True)], TOPICS, NOW)
    assert [q["learner_name"] for q in out["quiet_learners"]] == ["Bongani", "Chloe"]


def test_practice_set_prefers_questions_not_yet_mastered():
    q = [uuid.uuid4() for _ in range(7)]
    picked = make_practice_question_ids(q, recently_correct={q[0], q[1]}, size=5)
    assert picked == q[2:7]
    topped_up = make_practice_question_ids(q[:3], recently_correct={q[0]}, size=5)
    assert topped_up == [q[1], q[2], q[0]]
