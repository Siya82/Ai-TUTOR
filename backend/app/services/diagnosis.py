"""
Recursive root-cause diagnosis. See docs/ADR-007-root-cause-diagnosis.md.

REBUILD NOTE: this module's source was never recovered verbatim -- this
is a rebuild from REBUILD_SPEC.md Section 1 plus the matching ADR, not
recovered code. The exact mastery thresholds below
(MASTERY_ACCURACY_THRESHOLD, MIN_ATTEMPTS_FOR_CONFIRMED_MASTERY) are this
rebuild's own reasonable choice, not recovered values -- tune them
against real learner data once there is any.
"""

import uuid
from dataclasses import dataclass, field

from app.models import Attempt, Topic

MASTERY_ACCURACY_THRESHOLD = 0.6
MIN_ATTEMPTS_FOR_CONFIRMED_MASTERY = 3


@dataclass
class DiagnosisStep:
    topic_id: uuid.UUID
    topic_name: str
    attempt_count: int
    accuracy: float | None
    status: str  # "confirmed_mastery" | "insufficient" | "unconfirmed"
    reason: str


@dataclass
class DiagnosisResult:
    recommended_topic: Topic
    redirected: bool
    steps: list[DiagnosisStep] = field(default_factory=list)

    @property
    def reasoning_trace(self) -> list[str]:
        """Human-readable reasoning trace, in the order topics were checked."""
        return [step.reason for step in self.steps]


def _accuracy(attempts: list[Attempt]) -> float | None:
    scored = [a for a in attempts if a.is_correct is not None]
    if not scored:
        return None
    return sum(1 for a in scored if a.is_correct) / len(scored)


def diagnose_root_gap(
    prerequisite_chain: list[Topic],
    attempts_by_topic: dict[uuid.UUID, list[Attempt]],
) -> DiagnosisResult:
    """
    prerequisite_chain: ordered from the topic the learner asked about
    (index 0) back through its resolved Topic.prerequisite_id chain, with
    the deepest/most foundational topic last. The caller resolves this
    chain (repeated prerequisite_id lookups); this function does not
    query the database, which keeps it pure and directly testable
    (ADR-007).

    attempts_by_topic: pre-fetched attempts for the SAME learner, keyed
    by topic id, for every topic in the chain. Unscored attempts
    (is_correct is None) are ignored internally.

    Walks the chain checking mastery at each step. A topic with
    confirmed solid mastery (enough attempts AND accuracy at/above
    MASTERY_ACCURACY_THRESHOLD) stops the walk -- no need to go deeper.
    Unconfirmed mastery (fewer than MIN_ATTEMPTS_FOR_CONFIRMED_MASTERY
    scored attempts) is treated as a possible gap, not a pass, and the
    walk continues. The recommended teaching start point is the deepest
    topic encountered with insufficient or unconfirmed mastery -- which
    may be the originally requested topic itself if everything deeper is
    already mastered.
    """
    if not prerequisite_chain:
        raise ValueError("prerequisite_chain must contain at least the requested topic")

    requested_topic = prerequisite_chain[0]
    steps: list[DiagnosisStep] = []
    deepest_gap: Topic | None = None

    for topic in prerequisite_chain:
        attempts = attempts_by_topic.get(topic.id, [])
        scored = [a for a in attempts if a.is_correct is not None]
        attempt_count = len(scored)
        accuracy = _accuracy(attempts)

        if attempt_count < MIN_ATTEMPTS_FOR_CONFIRMED_MASTERY:
            reason = (
                f"{topic.name}: only {attempt_count} scored attempt(s) -- too few to "
                f"confirm mastery, treated as a possible gap, not a pass."
            )
            steps.append(DiagnosisStep(topic.id, topic.name, attempt_count, accuracy, "unconfirmed", reason))
            deepest_gap = topic
            continue

        if accuracy is not None and accuracy >= MASTERY_ACCURACY_THRESHOLD:
            reason = (
                f"{topic.name}: {accuracy:.0%} accuracy over {attempt_count} attempts -- "
                f"confirmed solid mastery, stopping here."
            )
            steps.append(DiagnosisStep(topic.id, topic.name, attempt_count, accuracy, "confirmed_mastery", reason))
            break

        reason = (
            f"{topic.name}: {accuracy:.0%} accuracy over {attempt_count} attempts -- "
            f"below the {MASTERY_ACCURACY_THRESHOLD:.0%} mastery threshold."
        )
        steps.append(DiagnosisStep(topic.id, topic.name, attempt_count, accuracy, "insufficient", reason))
        deepest_gap = topic

    recommended = deepest_gap if deepest_gap is not None else requested_topic
    redirected = recommended.id != requested_topic.id

    return DiagnosisResult(recommended_topic=recommended, redirected=redirected, steps=steps)
