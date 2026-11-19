"""ADR-039: INSIGHTS aggregation rules (privacy suppression, bands, ranking)."""

from app.services.insights import MIN_LEARNERS, GroupStats, band, present, weakest


def test_small_groups_are_suppressed():
    row = present(GroupStats("c", "10A", MIN_LEARNERS - 1, 40, 30), enrolled=4)
    assert row["suppressed"] is True
    assert row["accuracy"] is None and row["answered"] is None and row["participation"] is None


def test_present_computes_accuracy_and_participation():
    row = present(GroupStats("s", "School", 10, 100, 65), enrolled=20)
    assert row["accuracy"] == 65 and row["band"] == "watch" and row["participation"] == 50


def test_bands():
    assert band(None) is None
    assert band(70) == "good" and band(69) == "watch" and band(49) == "concern"


def test_weakest_needs_enough_answers_and_learners():
    rows = [
        GroupStats("a", "A", 10, 50, 10),   # 20%
        GroupStats("b", "B", 10, 50, 40),   # 80%
        GroupStats("c", "C", 10, 5, 0),     # too few answers
        GroupStats("d", "D", 2, 50, 0),     # too few learners
    ]
    out = weakest(rows)
    assert [r["label"] for r in out] == ["A", "B"]
