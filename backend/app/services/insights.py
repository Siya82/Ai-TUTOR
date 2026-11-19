"""
NEW 19 Nov 2026 (ADR-039, INSIGHTS).

Pure helpers for circuit/district dashboards. Officials see learning
outcomes aggregated by school, grade, subject, topic and class -- never an
individual learner. Two protections keep it that way:

- MIN_LEARNERS: any group with answers from fewer than this many learners
  is shown as "too few learners" instead of a number, so a small class or
  a single learner can't be singled out (POPIA data minimisation).
- Only counts and percentages leave the database layer; no names.
"""

from __future__ import annotations

from dataclasses import dataclass

WINDOW_DAYS = 30
MIN_LEARNERS = 5
MIN_TOPIC_ANSWERS = 10


@dataclass(frozen=True)
class GroupStats:
    key: str  # e.g. school id, "12|Pure Mathematics", topic id, class id
    label: str
    learners: int  # distinct learners who answered
    answered: int
    correct: int
    extra: dict | None = None


def band(accuracy: int | None) -> str | None:
    if accuracy is None:
        return None
    if accuracy >= 70:
        return "good"
    if accuracy >= 50:
        return "watch"
    return "concern"


def present(stats: GroupStats, enrolled: int | None = None) -> dict:
    """One row for the dashboard, with small groups suppressed."""
    suppressed = stats.learners < MIN_LEARNERS
    accuracy = None if suppressed or stats.answered == 0 else round(100 * stats.correct / stats.answered)
    row = {
        "key": stats.key,
        "label": stats.label,
        "suppressed": suppressed,
        "learners_active": None if suppressed else stats.learners,
        "answered": None if suppressed else stats.answered,
        "accuracy": accuracy,
        "band": band(accuracy),
    }
    if enrolled is not None:
        row["learners_enrolled"] = enrolled
        row["participation"] = (
            None if suppressed or enrolled == 0 else round(100 * stats.learners / enrolled)
        )
    if stats.extra:
        row.update(stats.extra)
    return row


def weakest(rows: list[GroupStats], limit: int = 8, min_answers: int = MIN_TOPIC_ANSWERS) -> list[dict]:
    """Topics with enough answers (and learners), lowest accuracy first."""
    eligible = [r for r in rows if r.answered >= min_answers and r.learners >= MIN_LEARNERS]
    eligible.sort(key=lambda r: (r.correct / r.answered, -r.answered))
    return [present(r) for r in eligible[:limit]]
