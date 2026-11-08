"""
Early-warning risk assessment. See docs/ADR-004-risk-model.md for why this
is a rule-based, fully-explainable v1 rather than a trained ML model --
there is no historical outcome data yet to train one honestly on.

RECOVERY NOTE: reconstructed verbatim from a read performed on 2026-08-26.
A second, near-duplicate module (`app/services/risk.py`, the original
ADR-004 implementation) also existed in the codebase alongside this one --
`dashboard.py` imports from THIS module (`risk_assessment.py`), not the
other. On rebuild, consolidate into one shared module rather than
re-forking two copies of the same three-signal logic.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

from app.models import Attempt, Topic


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class RiskAssessment:
    level: RiskLevel
    factors: list[str] = field(default_factory=list)
    recommended_interventions: list[str] = field(default_factory=list)


TREND_WINDOW_DAYS = 7
INACTIVITY_THRESHOLD_DAYS = 10
PREREQUISITE_MASTERY_THRESHOLD = 0.6
ACCURACY_DROP_THRESHOLD = 0.15


def _accuracy(attempts: list[Attempt]) -> float | None:
    scored = [a for a in attempts if a.is_correct is not None]
    if not scored:
        return None
    return sum(1 for a in scored if a.is_correct) / len(scored)


def assess_risk(
    learner_attempts: list[Attempt],
    topic: Topic,
    prerequisite_attempts: list[Attempt] | None = None,
    now: datetime | None = None,
) -> RiskAssessment:
    """
    Combines three interpretable signals into a risk level.
    """
    now = now or datetime.utcnow()
    factors: list[str] = []
    interventions: list[str] = []

    recent = [a for a in learner_attempts if now - a.created_at <= timedelta(days=TREND_WINDOW_DAYS)]
    previous = [
        a
        for a in learner_attempts
        if timedelta(days=TREND_WINDOW_DAYS) < now - a.created_at <= timedelta(days=2 * TREND_WINDOW_DAYS)
    ]

    recent_acc = _accuracy(recent)
    previous_acc = _accuracy(previous)

    if recent_acc is not None and previous_acc is not None and recent_acc < previous_acc - ACCURACY_DROP_THRESHOLD:
        factors.append(
            f"Accuracy on {topic.name} dropped from {previous_acc:.0%} to {recent_acc:.0%} "
            f"over the last {TREND_WINDOW_DAYS} days."
        )
        interventions.append(f"Flag {topic.name} for teacher review — recent accuracy decline.")

    if prerequisite_attempts is not None:
        prereq_acc = _accuracy(prerequisite_attempts)
        if prereq_acc is not None and prereq_acc < PREREQUISITE_MASTERY_THRESHOLD:
            factors.append(
                f"Weak mastery ({prereq_acc:.0%}) of the prerequisite topic before starting "
                f"{topic.name} — likely to struggle here even before attempting it."
            )
            interventions.append(
                f"Recommend revisiting the prerequisite topic before advancing further into {topic.name}."
            )

    if learner_attempts:
        last_attempt_at = max(a.created_at for a in learner_attempts)
        gap_days = (now - last_attempt_at).days
        if gap_days >= INACTIVITY_THRESHOLD_DAYS:
            factors.append(f"No activity in {gap_days} days, following a period of engagement.")
            interventions.append("Recommend a check-in — disengagement is often an early failure signal.")

    if len(factors) >= 2:
        level = RiskLevel.HIGH
    elif len(factors) == 1:
        level = RiskLevel.MEDIUM
    else:
        level = RiskLevel.LOW

    return RiskAssessment(level=level, factors=factors, recommended_interventions=interventions)
