"""ADR-038: the parent view's pure rules."""

import uuid
from datetime import datetime, timedelta

from app.services.connect import MarkedAnswer, WorkItem, child_overview, summary_text

NOW = datetime(2026, 11, 19, 7, 0)
T1, T2 = uuid.uuid4(), uuid.uuid4()


def a(tid, name, ok, days=1):
    return MarkedAnswer(tid, name, "Pure Mathematics", ok, NOW - timedelta(days=days))


def test_week_stats_and_topics():
    answers = [a(T1, "Exponents", True), a(T1, "Exponents", True), a(T1, "Exponents", False),
               a(T2, "Functions", False), a(T2, "Functions", False), a(T2, "Functions", True, days=20)]
    o = child_overview("Lerato", answers, [], NOW)
    assert o["week"]["answered"] == 5
    assert o["week"]["accuracy"] == 40
    assert o["weakest_topics"][0]["topic_name"] == "Functions"


def test_topics_need_three_answers():
    o = child_overview("Lerato", [a(T1, "Exponents", False), a(T1, "Exponents", False)], [], NOW)
    assert o["weakest_topics"] == [] and o["strongest_topics"] == []


def test_outstanding_work_counts_unfinished_only():
    work = [
        WorkItem("Test 1", ("Pure Mathematics",), "test", NOW + timedelta(days=2), "in_progress", None, 10),
        WorkItem("Practice", ("Pure Mathematics",), "practice", None, "completed", 4, 5),
    ]
    o = child_overview("Lerato", [], work, NOW)
    assert o["outstanding_count"] == 1
    assert o["work"][0]["marks_earned"] is None  # unreleased test stays hidden


def test_summary_text_reads_naturally():
    o = child_overview("Lerato", [], [], NOW)
    text = summary_text(o)
    assert "Lerato didn't answer any practice questions" in text
    assert "no unfinished school work" in text
