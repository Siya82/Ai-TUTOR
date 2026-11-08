"""
Unit tests for app.services.personalization. Pure -- no DB needed.
"""

from datetime import datetime, timedelta

from app.models import Attempt
from app.services.personalization import (
    build_personalization_instructions,
    compute_pace_tier,
)


def _attempts(n_correct: int, n_wrong: int, days_ago: int = 1) -> list[Attempt]:
    when = datetime.utcnow() - timedelta(days=days_ago)
    return (
        [Attempt(is_correct=True, created_at=when) for _ in range(n_correct)]
        + [Attempt(is_correct=False, created_at=when) for _ in range(n_wrong)]
    )


def test_defaults_to_on_pace_with_too_few_recent_attempts():
    now = datetime.utcnow()
    assert compute_pace_tier(_attempts(1, 0), now=now) == "on_pace"


def test_needs_support_on_low_accuracy():
    now = datetime.utcnow()
    assert compute_pace_tier(_attempts(1, 4), now=now) == "needs_support"


def test_ready_for_extension_on_high_accuracy():
    now = datetime.utcnow()
    assert compute_pace_tier(_attempts(9, 1), now=now) == "ready_for_extension"


def test_on_pace_in_the_middle():
    now = datetime.utcnow()
    assert compute_pace_tier(_attempts(6, 4), now=now) == "on_pace"


def test_attempts_older_than_the_window_are_excluded():
    now = datetime.utcnow()
    stale = _attempts(1, 9, days_ago=20)  # would be needs_support if counted
    assert compute_pace_tier(stale, now=now) == "on_pace"


def test_unscored_attempts_are_excluded():
    now = datetime.utcnow()
    unscored = [Attempt(is_correct=None, created_at=now - timedelta(days=1)) for _ in range(5)]
    assert compute_pace_tier(unscored, now=now) == "on_pace"


def test_personalization_block_mentions_both_signals():
    block = build_personalization_instructions("visual", "needs_support")
    assert "visual" in block.lower()
    assert "slow down" in block.lower()


def test_personalization_block_falls_back_on_unknown_values():
    block = build_personalization_instructions("not-a-real-modality", "not-a-real-tier")
    assert "no stated presentation preference" in block.lower()
    assert "normal pace" in block.lower()
