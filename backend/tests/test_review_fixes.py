"""Tests for the 17 Nov 2026 code-review fixes (docs/CODE_REVIEW_2026-11-17.md)."""

from datetime import datetime, timedelta
from types import SimpleNamespace

from app.services.assignments import answers_closed_reason
from app.services.tutor import trim_history


def _assignment(mode="test", released=False, due_at=None):
    return SimpleNamespace(mode=mode, results_released=released, due_at=due_at)


NOW = datetime(2026, 11, 17, 12, 0)


def test_practice_never_closes():
    a = _assignment(mode="practice", released=True, due_at=NOW - timedelta(days=3))
    assert answers_closed_reason(a, now=NOW) is None


def test_open_test_accepts_answers():
    assert answers_closed_reason(_assignment(due_at=NOW + timedelta(hours=1)), now=NOW) is None
    assert answers_closed_reason(_assignment(), now=NOW) is None


def test_released_test_is_closed():
    assert "released" in answers_closed_reason(_assignment(released=True), now=NOW)


def test_overdue_test_is_closed():
    assert "due date" in answers_closed_reason(_assignment(due_at=NOW - timedelta(minutes=1)), now=NOW)


def _msgs(n):
    return [{"role": "user" if i % 2 == 0 else "assistant", "content": str(i)} for i in range(n)]


def test_trim_history_keeps_short_conversations():
    assert trim_history(_msgs(5), 20) == _msgs(5)


def test_trim_history_caps_and_starts_on_user():
    out = trim_history(_msgs(41), 20)
    assert len(out) <= 20
    assert out[0]["role"] == "user"
    assert out[-1] == _msgs(41)[-1]


def test_trim_history_drops_leading_assistant():
    out = trim_history(_msgs(10), 5)  # last 5 = a,u,a,u,a? -> starts with user after trim
    assert out[0]["role"] == "user"


# --- code review #6 / #17: login throttling, bcrypt without passlib ----------

from app.services.auth import create_access_token, decode_access_token, hash_password, verify_password

# A hash made by passlib (the old code path) -- existing users' passwords must
# keep working after the switch to bcrypt directly.
PASSLIB_HASH = "$2b$12$bzKH4yjS49RBosWQn3hJZ.IGVCNNz70WxXVsJnYDziynvxnWMB84m"


def test_existing_passlib_hashes_still_verify():
    assert verify_password("DevPass123!", PASSLIB_HASH)
    assert not verify_password("wrong", PASSLIB_HASH)


def test_new_hashes_round_trip_and_bad_hash_is_false():
    h = hash_password("NewPass123!")
    assert verify_password("NewPass123!", h)
    assert not verify_password("NewPass123!", "not-a-bcrypt-hash")


def test_token_carries_version():
    payload = decode_access_token(create_access_token("u1", "student", 3))
    assert payload["ver"] == 3
