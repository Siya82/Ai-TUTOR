"""
Class progress aggregation for THUTOra TEACH's Progress tab.

NEW 17 Nov 2026 (ADR-030, class progress dashboard). Pure functions only --
no database access -- so the whole aggregation is unit-testable with plain
in-memory objects, the same pure/DB split app/services/admin.py uses for
CSV parsing. app/services/dashboard.py does the (two) queries and hands
the rows to these functions.

Why this exists instead of reusing get_dashboard_summary() per learner:
the original single-learner detail path ran 1-2 queries PER TOPIC to
build risk assessments (an N+1 the 26 Aug report already warned about),
and computed risk for every topic in the learner's grade -- including
topics they had never touched and whose prerequisite they had never
touched either, which can only ever come back "low" and just pads the
list. Here risk is computed in memory, once, over a "candidate" set:
topics the learner has actually attempted, plus topics whose direct
prerequisite they have attempted (ADR-004's prerequisite signal can
legitimately flag a topic BEFORE the learner starts it -- that is the
point of an early warning). Everything else is skipped, not faked.

The risk rules themselves are untouched -- assess_risk() from
risk_assessment.py is called exactly as before (it duck-types on
.is_correct/.created_at for attempts and .name for the topic).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable, Optional
from uuid import UUID

from app.services.risk_assessment import (
    PREREQUISITE_MASTERY_THRESHOLD,
    RiskLevel,
    assess_risk,
)

# A learner counts as "struggling" on a topic below this accuracy -- the
# same 60% line ADR-004 already uses for "weak prerequisite mastery", so
# the Progress tab and the risk model agree on what "weak" means.
STRUGGLING_ACCURACY_THRESHOLD = PREREQUISITE_MASTERY_THRESHOLD
# Fewer scored attempts than this on a topic and we don't call anyone
# "struggling" there yet -- one wrong answer is not a pattern.
MIN_ATTEMPTS_FOR_STRUGGLING = 2
ACTIVE_WINDOW_DAYS = 7

_RISK_ORDER = {RiskLevel.LOW.value: 0, RiskLevel.MEDIUM.value: 1, RiskLevel.HIGH.value: 2}


@dataclass(frozen=True)
class LearnerRow:
    id: UUID
    name: str
    grade: int


@dataclass(frozen=True)
class AttemptRow:
    """One scored attempt, flattened to just what aggregation needs."""

    learner_id: UUID
    topic_id: UUID
    is_correct: Optional[bool]
    created_at: datetime


@dataclass(frozen=True)
class TopicRow:
    id: UUID
    name: str
    prerequisite_id: Optional[UUID]
    subject_name: str
    grade: int
    order_index: int = 0
    subject_id: Optional[UUID] = None  # NEW (ADR-031): lets callers filter attempts by subject scope


def _accuracy(attempts: Iterable[AttemptRow]) -> Optional[float]:
    scored = [a for a in attempts if a.is_correct is not None]
    if not scored:
        return None
    return round(sum(1 for a in scored if a.is_correct) / len(scored), 2)


def _topic_sort_key(t: TopicRow):
    return (t.grade, t.subject_name, t.order_index, t.name)


def assess_learner_topics(
    learner: LearnerRow,
    attempts: list[AttemptRow],
    topics: dict[UUID, TopicRow],
    now: Optional[datetime] = None,
) -> list[dict]:
    """
    Risk for one learner across their candidate topics (see module
    docstring). `attempts` must be this learner's scored attempts only.
    Returns every candidate topic's assessment (low included), sorted
    highest risk first; callers filter to non-low for "flagged".
    """
    now = now or datetime.utcnow()
    by_topic: dict[UUID, list[AttemptRow]] = {}
    for a in attempts:
        by_topic.setdefault(a.topic_id, []).append(a)

    attempted = set(by_topic)
    candidates = set(attempted)
    for t in topics.values():
        if t.prerequisite_id in attempted and t.grade <= learner.grade:
            candidates.add(t.id)

    results = []
    for topic_id in candidates:
        topic = topics.get(topic_id)
        if topic is None:
            continue  # attempt on a topic that no longer exists -- skip, don't crash
        prereq_attempts = (
            by_topic.get(topic.prerequisite_id) if topic.prerequisite_id else None
        )
        risk = assess_risk(
            learner_attempts=by_topic.get(topic_id, []),
            topic=topic,
            prerequisite_attempts=prereq_attempts,
            now=now,
        )
        results.append(
            {
                "learner_id": str(learner.id),
                "topic_id": str(topic.id),
                "topic_name": topic.name,
                "subject_name": topic.subject_name,
                "grade": topic.grade,
                "risk_level": risk.level.value,
                "factors": risk.factors,
                "interventions": risk.recommended_interventions,
            }
        )
    results.sort(
        key=lambda r: (-_RISK_ORDER[r["risk_level"]], r["grade"], r["subject_name"], r["topic_name"])
    )
    return results


def summarize_class_progress(
    learners: list[LearnerRow],
    attempts: list[AttemptRow],
    topics: dict[UUID, TopicRow],
    now: Optional[datetime] = None,
) -> dict:
    """
    The whole Progress-tab payload: a class summary, one row per
    learner (with their highest risk and flagged topics), and one row
    per topic the class has actually attempted (so the teacher can see
    WHERE the class is weak, not just WHO is).
    """
    now = now or datetime.utcnow()
    learner_ids = {l.id for l in learners}
    scored = [a for a in attempts if a.is_correct is not None and a.learner_id in learner_ids]

    by_learner: dict[UUID, list[AttemptRow]] = {}
    for a in scored:
        by_learner.setdefault(a.learner_id, []).append(a)

    learner_rows = []
    for learner in learners:
        mine = by_learner.get(learner.id, [])
        assessments = assess_learner_topics(learner, mine, topics, now=now)
        flagged = [r for r in assessments if r["risk_level"] != RiskLevel.LOW.value]
        overall = flagged[0]["risk_level"] if flagged else RiskLevel.LOW.value
        last = max((a.created_at for a in mine), default=None)
        learner_rows.append(
            {
                "id": str(learner.id),
                "name": learner.name,
                "grade": learner.grade,
                "total_attempts": len(mine),
                "overall_accuracy": _accuracy(mine),
                "last_activity": last.isoformat() if last else None,
                "risk_level": overall if mine else None,  # None = no data yet, not "low"
                "flagged_topics": [
                    {"topic_id": r["topic_id"], "topic_name": r["topic_name"], "risk_level": r["risk_level"]}
                    for r in flagged
                ],
            }
        )
    # Highest risk first, then least active, then name -- the order a
    # teacher would actually want to work down the list in.
    learner_rows.sort(
        key=lambda r: (
            -(_RISK_ORDER[r["risk_level"]] if r["risk_level"] else -1),
            r["overall_accuracy"] if r["overall_accuracy"] is not None else 2,
            r["name"],
        )
    )

    by_topic: dict[UUID, list[AttemptRow]] = {}
    for a in scored:
        by_topic.setdefault(a.topic_id, []).append(a)

    topic_rows = []
    for topic_id, rows in by_topic.items():
        topic = topics.get(topic_id)
        if topic is None:
            continue
        per_learner: dict[UUID, list[AttemptRow]] = {}
        for a in rows:
            per_learner.setdefault(a.learner_id, []).append(a)
        struggling = [
            lid
            for lid, la in per_learner.items()
            if len(la) >= MIN_ATTEMPTS_FOR_STRUGGLING
            and (_accuracy(la) or 0) < STRUGGLING_ACCURACY_THRESHOLD
        ]
        topic_rows.append(
            (
                topic,
                {
                    "topic_id": str(topic.id),
                    "topic_name": topic.name,
                    "subject_name": topic.subject_name,
                    "grade": topic.grade,
                    "learners_attempted": len(per_learner),
                    "attempt_count": len(rows),
                    "accuracy": _accuracy(rows),
                    "struggling_learners": len(struggling),
                },
            )
        )
    topic_rows.sort(key=lambda pair: _topic_sort_key(pair[0]))

    active_cutoff = now - timedelta(days=ACTIVE_WINDOW_DAYS)
    summary = {
        "total_learners": len(learners),
        "active_learners": sum(
            1 for l in learners if any(a.created_at >= active_cutoff for a in by_learner.get(l.id, []))
        ),
        "learners_with_no_attempts": sum(1 for l in learners if not by_learner.get(l.id)),
        "high_risk_learners": sum(1 for r in learner_rows if r["risk_level"] == RiskLevel.HIGH.value),
        "medium_risk_learners": sum(1 for r in learner_rows if r["risk_level"] == RiskLevel.MEDIUM.value),
        "class_accuracy": _accuracy(scored),
        "active_window_days": ACTIVE_WINDOW_DAYS,
    }
    return {
        "summary": summary,
        "learners": learner_rows,
        "topics": [row for _, row in topic_rows],
    }
