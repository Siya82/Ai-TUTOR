"""
Tests for app/services/class_progress.py (ADR-030, TEACH class progress
dashboard). Pure -- no DB, no network -- same as test_admin.py.
"""

import uuid
from datetime import datetime, timedelta

from app.services.class_progress import (
    AttemptRow,
    LearnerRow,
    TopicRow,
    assess_learner_topics,
    summarize_class_progress,
)

NOW = datetime(2026, 11, 17, 9, 0, 0)

ALGEBRA = uuid.uuid4()
EQUATIONS = uuid.uuid4()  # prerequisite: ALGEBRA
FUNCTIONS = uuid.uuid4()  # prerequisite: EQUATIONS
G12_CALC = uuid.uuid4()  # grade 12, prerequisite: ALGEBRA

TOPICS = {
    ALGEBRA: TopicRow(ALGEBRA, "Algebraic Expressions", None, "Pure Mathematics", 10, 0),
    EQUATIONS: TopicRow(EQUATIONS, "Equations and Inequalities", ALGEBRA, "Pure Mathematics", 10, 2),
    FUNCTIONS: TopicRow(FUNCTIONS, "Functions", EQUATIONS, "Pure Mathematics", 10, 5),
    G12_CALC: TopicRow(G12_CALC, "Differential Calculus", ALGEBRA, "Pure Mathematics", 12, 3),
}


def _attempts(learner_id, topic_id, outcomes, days_ago=1):
    return [
        AttemptRow(learner_id, topic_id, ok, NOW - timedelta(days=days_ago, minutes=i))
        for i, ok in enumerate(outcomes)
    ]


def test_weak_prerequisite_flags_next_topic_before_it_is_attempted():
    thandi = LearnerRow(uuid.uuid4(), "Thandi", 10)
    attempts = _attempts(thandi.id, ALGEBRA, [False, False, True])  # 33%
    result = assess_learner_topics(thandi, attempts, TOPICS, now=NOW)
    by_topic = {r["topic_id"]: r for r in result}

    # Equations is flagged from the weak prerequisite alone (ADR-004 signal 2)
    assert by_topic[str(EQUATIONS)]["risk_level"] == "medium"
    assert "prerequisite" in by_topic[str(EQUATIONS)]["factors"][0]
    # Functions: its prerequisite (Equations) was never attempted -> not a candidate
    assert str(FUNCTIONS) not in by_topic
    # Grade 12 topic is out of a Grade 10 learner's reach -> not assessed
    assert str(G12_CALC) not in by_topic
    # Highest risk sorts first
    assert result[0]["risk_level"] == "medium"


def test_untouched_learner_has_no_risk_level_not_low():
    ghost = LearnerRow(uuid.uuid4(), "Ghost", 10)
    data = summarize_class_progress([ghost], [], TOPICS, now=NOW)
    row = data["learners"][0]
    assert row["risk_level"] is None
    assert row["total_attempts"] == 0
    assert row["overall_accuracy"] is None
    assert data["summary"]["learners_with_no_attempts"] == 1
    assert data["summary"]["class_accuracy"] is None
    assert data["topics"] == []


def test_class_summary_topics_and_ordering():
    strong = LearnerRow(uuid.uuid4(), "Amahle", 10)
    weak = LearnerRow(uuid.uuid4(), "Bongani", 10)
    idle = LearnerRow(uuid.uuid4(), "Cebo", 10)
    attempts = (
        _attempts(strong.id, ALGEBRA, [True, True, True])
        + _attempts(strong.id, EQUATIONS, [True, True])
        + _attempts(weak.id, ALGEBRA, [False, False, True])
        + _attempts(weak.id, EQUATIONS, [False, False])
        # an unmarked attempt (is_correct=None) must be ignored everywhere
        + [AttemptRow(weak.id, EQUATIONS, None, NOW)]
    )
    data = summarize_class_progress([idle, strong, weak], attempts, TOPICS, now=NOW)

    # Riskiest learner first, untouched learner last
    names = [r["name"] for r in data["learners"]]
    assert names[0] == "Bongani"
    assert names[-1] == "Cebo"

    bongani = data["learners"][0]
    assert bongani["total_attempts"] == 5  # the unmarked attempt is excluded
    assert bongani["overall_accuracy"] == 0.2
    assert bongani["risk_level"] in ("medium", "high")
    assert any(f["topic_name"] == "Equations and Inequalities" for f in bongani["flagged_topics"])

    amahle = next(r for r in data["learners"] if r["name"] == "Amahle")
    assert amahle["risk_level"] == "low"
    assert amahle["flagged_topics"] == []

    # Topics in CAPS order, with class accuracy and struggling counts
    topics = data["topics"]
    assert [t["topic_name"] for t in topics] == ["Algebraic Expressions", "Equations and Inequalities"]
    algebra = topics[0]
    assert algebra["learners_attempted"] == 2
    assert algebra["attempt_count"] == 6
    assert algebra["accuracy"] == 0.67
    assert algebra["struggling_learners"] == 1  # Bongani at 33%

    s = data["summary"]
    assert s["total_learners"] == 3
    assert s["active_learners"] == 2
    assert s["learners_with_no_attempts"] == 1
    assert s["class_accuracy"] == 0.6


def test_single_wrong_answer_is_not_struggling():
    learner = LearnerRow(uuid.uuid4(), "Dumi", 10)
    data = summarize_class_progress(
        [learner], _attempts(learner.id, ALGEBRA, [False]), TOPICS, now=NOW
    )
    assert data["topics"][0]["struggling_learners"] == 0


def test_inactivity_and_prereq_combine_to_high():
    learner = LearnerRow(uuid.uuid4(), "Esihle", 10)
    attempts = _attempts(learner.id, ALGEBRA, [False, False, False], days_ago=12) + _attempts(
        learner.id, EQUATIONS, [True], days_ago=12
    )
    result = assess_learner_topics(learner, attempts, TOPICS, now=NOW)
    equations = next(r for r in result if r["topic_id"] == str(EQUATIONS))
    assert equations["risk_level"] == "high"  # weak prereq + 12 days inactive


def test_attempts_from_other_learners_or_unknown_topics_are_ignored():
    mine = LearnerRow(uuid.uuid4(), "Fezile", 10)
    stranger = uuid.uuid4()
    attempts = _attempts(stranger, ALGEBRA, [False, False]) + _attempts(mine.id, uuid.uuid4(), [True])
    data = summarize_class_progress([mine], attempts, TOPICS, now=NOW)
    assert data["topics"] == []  # the unknown topic is skipped, the stranger excluded
    assert data["learners"][0]["total_attempts"] == 1
