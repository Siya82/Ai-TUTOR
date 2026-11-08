"""
Unit tests for app.services.tutor_orchestration.prepare_tutor_turn().
Pure -- no DB needed, Learner/Topic/Attempt are constructed directly.
"""

import uuid
from datetime import datetime, timedelta

from app.models import Attempt, Learner, Topic
from app.services.tutor_orchestration import prepare_tutor_turn


def _topic(name: str, prerequisite_id=None) -> Topic:
    return Topic(id=uuid.uuid4(), subject_id=uuid.uuid4(), name=name, prerequisite_id=prerequisite_id)


def _learner(preferred_modality: str = "balanced") -> Learner:
    return Learner(
        id=uuid.uuid4(), display_name="Test Learner", grade=10, preferred_modality=preferred_modality
    )


def _attempts(n_correct: int, n_wrong: int) -> list[Attempt]:
    when = datetime.utcnow() - timedelta(days=1)
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
