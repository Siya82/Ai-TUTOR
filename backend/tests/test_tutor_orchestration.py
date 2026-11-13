"""
Unit tests for app.services.tutor_orchestration.prepare_tutor_turn().
Pure -- no DB needed, Learner/Topic/Attempt are constructed directly.

FIX 13 Nov 2026 (multi-subject support, ADR-013 follow-up, found via a
real pytest run after adding Physical Sciences -- not anticipated in
ADR-013's own "Consequences" section, which only flagged a live-call
risk): prepare_tutor_turn() now reads recommended_topic.subject.name/
.grade, which routers/tutor.py guarantees via selectinload(Topic.subject)
against a real DB session -- but _topic() here builds a detached Topic
with no session at all, so .subject was simply None, not lazy-loadable.
Fixed by having _topic() attach a real in-memory Subject directly
(assigning a relationship attribute on a transient object needs no
session), rather than loosening prepare_tutor_turn()'s real contract to
tolerate a subject-less Topic it will never actually see in production.
"""

import uuid
from datetime import UTC, datetime, timedelta


# Matches app.services.personalization._now_naive(): datetime.now(UTC) (not the deprecated _now_naive()), made naive to match Attempt.created_at's naive _now_naive() default.
def _now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)

from app.models import Attempt, Learner, Subject, Topic
from app.services.tutor_orchestration import prepare_tutor_turn


# Shared in-memory Subject -- mirrors what routers/tutor.py's
# selectinload(Topic.subject) actually hands prepare_tutor_turn() in
# production (a real Subject, not None). One default instance is enough
# since every test below is Pure Mathematics content.
_DEFAULT_SUBJECT = Subject(id=uuid.uuid4(), name="Pure Mathematics", grade=10)


def _topic(name: str, prerequisite_id=None, subject: Subject | None = None) -> Topic:
    topic = Topic(id=uuid.uuid4(), subject_id=uuid.uuid4(), name=name, prerequisite_id=prerequisite_id)
    topic.subject = subject or _DEFAULT_SUBJECT
    return topic


def _learner(preferred_modality: str = "balanced") -> Learner:
    return Learner(
        id=uuid.uuid4(), display_name="Test Learner", grade=10, preferred_modality=preferred_modality
    )


def _attempts(n_correct: int, n_wrong: int) -> list[Attempt]:
    when = _now_naive() - timedelta(days=1)
    return (
        [Attempt(is_correct=True, created_at=when) for _ in range(n_correct)]
        + [Attempt(is_correct=False, created_at=when) for _ in range(n_wrong)]
    )


def test_no_redirect_teaches_the_requested_topic():
    mult = _topic("Multiplication of Algebraic Terms")
    factor = _topic("Factorisation", prerequisite_id=mult.id)
    quad = _topic("Quadratic Equations", prerequisite_id=factor.id)
    learner = _learner()

    prep = prepare_tutor_turn(learner, [quad, factor, mult], {factor.id: _attempts(9, 1)})

    assert prep.recommended_topic.id == quad.id
    assert prep.diagnosis.redirected is False
    assert "DIAGNOSIS NOTE" not in prep.system_prompt
    assert "Quadratic Equations" in prep.system_prompt


def test_redirect_adds_a_diagnosis_note_naming_both_topics():
    mult = _topic("Multiplication of Algebraic Terms")
    factor = _topic("Factorisation", prerequisite_id=mult.id)
    quad = _topic("Quadratic Equations", prerequisite_id=factor.id)
    learner = _learner()

    prep = prepare_tutor_turn(learner, [quad, factor, mult], {})  # no history anywhere -> redirect to root

    assert prep.recommended_topic.id == mult.id
    assert prep.diagnosis.redirected is True
    assert "DIAGNOSIS NOTE" in prep.system_prompt
    assert "Quadratic Equations" in prep.system_prompt  # the originally requested topic, named in the note
    assert "Multiplication of Algebraic Terms" in prep.system_prompt


def test_invalid_modality_falls_back_to_balanced_without_crashing():
    topic = _topic("Functions")
    learner = _learner(preferred_modality="some-legacy-garbage-value")

    prep = prepare_tutor_turn(learner, [topic], {})

    assert prep.modality_used == "balanced"


def test_pace_tier_is_computed_for_the_topic_actually_taught_not_the_requested_one():
    mult = _topic("Multiplication of Algebraic Terms")
    factor = _topic("Factorisation", prerequisite_id=mult.id)
    quad = _topic("Quadratic Equations", prerequisite_id=factor.id)
    learner = _learner()

    # No history on quad or factor -> redirect to mult. Strong recent accuracy on
    # mult specifically should drive pace_tier, not quad's (nonexistent) history.
    prep = prepare_tutor_turn(learner, [quad, factor, mult], {mult.id: _attempts(1, 9)})

    assert prep.recommended_topic.id == mult.id
    assert prep.pace_tier == "needs_support"


def test_subject_name_and_grade_come_from_the_topics_real_subject():
    """Regression test for the 13 Nov 2026 fix: prepare_tutor_turn() must
    read the SUBJECT actually attached to the topic being taught, not
    assume Pure Mathematics -- this is the orchestration-layer half of
    what test_tutor_prompt.py already checks at the prompt-builder layer."""
    physics = Subject(id=uuid.uuid4(), name="Physical Sciences", grade=10)
    topic = _topic("Motion in One Dimension", subject=physics)
    learner = _learner()

    prep = prepare_tutor_turn(learner, [topic], {})

    assert "Grade 10 Physical Sciences tutor" in prep.system_prompt
    assert "Mathematics" not in prep.system_prompt
