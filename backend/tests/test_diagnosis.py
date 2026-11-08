"""
Unit tests for app.services.diagnosis.diagnose_root_gap(), matching the
scenarios ADR-007 describes. Pure -- no DB, no event loop needed.
"""

import uuid
from datetime import datetime, timedelta

from app.models import Attempt, Topic
from app.services.diagnosis import diagnose_root_gap


def _topic(name: str, prerequisite_id=None) -> Topic:
    return Topic(id=uuid.uuid4(), subject_id=uuid.uuid4(), name=name, prerequisite_id=prerequisite_id)


def _attempts(n_correct: int, n_wrong: int, days_ago: int = 1) -> list[Attempt]:
    when = datetime.utcnow() - timedelta(days=days_ago)
    return (
        [Attempt(is_correct=True, created_at=when) for _ in range(n_correct)]
        + [Attempt(is_correct=False, created_at=when) for _ in range(n_wrong)]
    )


def _chain():
    mult = _topic("Multiplication of Algebraic Terms")
    factor = _topic("Factorisation", prerequisite_id=mult.id)
    quad = _topic("Quadratic Equations", prerequisite_id=factor.id)
    return [quad, factor, mult]


def test_no_gap_past_a_mastered_prerequisite():
    quad, factor, mult = _chain()
    attempts = {
        quad.id: _attempts(1, 4),    # 20% -- insufficient on the requested topic itself
        factor.id: _attempts(8, 1),  # ~89% -- confirmed mastery, should stop here
        mult.id: _attempts(0, 5),    # must never be reached
    }
    result = diagnose_root_gap([quad, factor, mult], attempts)
    assert result.recommended_topic.id == quad.id
    assert result.redirected is False
    assert len(result.steps) == 2
    assert result.steps[-1].status == "confirmed_mastery"


def test_redirects_to_the_deepest_unmastered_prerequisite():
    quad, factor, mult = _chain()
    attempts = {
        quad.id: _attempts(1, 4),
        factor.id: _attempts(1, 1),   # only 2 scored -- unconfirmed
        mult.id: _attempts(9, 1),     # confirmed mastery -- stop here
    }
    result = diagnose_root_gap([quad, factor, mult], attempts)
    assert result.recommended_topic.id == factor.id
    assert result.redirected is True
    assert result.steps[1].status == "unconfirmed"


def test_walks_all_the_way_to_the_root_with_no_history():
    quad, factor, mult = _chain()
    result = diagnose_root_gap([quad, factor, mult], {})
    assert result.recommended_topic.id == mult.id
    assert result.redirected is True
    assert all(step.status == "unconfirmed" for step in result.steps)


def test_confirmed_mastery_on_requested_topic_means_no_redirect():
    quad, factor, mult = _chain()
    attempts = {quad.id: _attempts(9, 1)}
    result = diagnose_root_gap([quad, factor, mult], attempts)
    assert result.recommended_topic.id == quad.id
    assert result.redirected is False
    assert len(result.steps) == 1


def test_single_topic_chain_never_redirects():
    quad, _, _ = _chain()
    result = diagnose_root_gap([quad], {quad.id: _attempts(1, 4)})
    assert result.recommended_topic.id == quad.id
    assert result.redirected is False


def test_empty_chain_raises():
    import pytest

    with pytest.raises(ValueError):
        diagnose_root_gap([], {})
