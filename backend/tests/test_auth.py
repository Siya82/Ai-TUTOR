"""
Tests for app/services/auth.py (ADR-017, student login). Pure -- no DB,
no network, no FastAPI app, matching every other service test in this
project (test_math_validator.py, test_attachments.py, ...).

provision_student() itself is NOT tested here since it needs a real
AsyncSession (it does uniqueness-checking queries against the users
table) -- that's an integration-test concern, not a unit one, and this
project's existing service tests draw that same line (e.g.
test_attachments.py's save_upload is DB-free but its router-level
persistence isn't unit-tested either). Covered here: every pure
helper -- hashing, token encode/decode, and the two random-value
generators.

NOTE for whoever runs this file: app.services.auth imports
app.core.config, whose Settings() now requires JWT_SECRET_KEY (no
default, same posture as ANTHROPIC_API_KEY) -- add it to backend/.env
before running pytest, or these tests (and anything else importing
app.core.config) fail at collection time with a pydantic
ValidationError, not a test failure.
"""

import time

import pytest
from jose import jwt

from app.core.config import settings
from app.services.auth import (
    create_access_token,
    decode_access_token,
    generate_student_number,
    generate_temp_password,
    hash_password,
    verify_password,
)


# ---------------------------------------------------------------------------
# hash_password / verify_password
# ---------------------------------------------------------------------------


def test_hash_password_round_trips_with_verify_password():
    raw = "DevPass123!"
    hashed = hash_password(raw)
    assert verify_password(raw, hashed) is True


def test_verify_password_rejects_wrong_password():
    hashed = hash_password("DevPass123!")
    assert verify_password("WrongPassword1", hashed) is False


def test_hash_password_never_stores_the_plaintext():
    raw = "DevPass123!"
    hashed = hash_password(raw)
    # The whole point of hashing -- a leaked password_hash column should
    # never directly contain the password it was made from.
    assert raw not in hashed


def test_hash_password_is_salted_so_two_hashes_of_the_same_password_differ():
    raw = "DevPass123!"
    assert hash_password(raw) != hash_password(raw)


# ---------------------------------------------------------------------------
# generate_temp_password / generate_student_number
# ---------------------------------------------------------------------------


def test_generate_temp_password_default_length():
    assert len(generate_temp_password()) == 10


def test_generate_temp_password_respects_custom_length():
    assert len(generate_temp_password(length=16)) == 16


def test_generate_temp_password_uses_only_letters_and_digits():
    pw = generate_temp_password(length=200)
    assert all(c.isalnum() for c in pw)


def test_generate_student_number_default_length_and_digits_only():
    number = generate_student_number()
    assert len(number) == 6
    assert number.isdigit()


def test_generate_student_number_respects_custom_length():
    number = generate_student_number(length=10)
    assert len(number) == 10
    assert number.isdigit()


def test_generate_temp_password_and_student_number_are_not_fixed_values():
    # Cheap randomness sanity check -- not a proof, but catches an
    # accidental hardcoded return value during a future refactor.
    values = {generate_temp_password() for _ in range(20)}
    assert len(values) > 1
    numbers = {generate_student_number() for _ in range(20)}
    assert len(numbers) > 1


# ---------------------------------------------------------------------------
# create_access_token / decode_access_token
# ---------------------------------------------------------------------------


def test_create_access_token_round_trips_through_decode_access_token():
    token = create_access_token(user_id="11111111-1111-1111-1111-111111111111", role="student")
    payload = decode_access_token(token)
    assert payload is not None
    assert payload["sub"] == "11111111-1111-1111-1111-111111111111"
    assert payload["role"] == "student"
    assert "exp" in payload


def test_decode_access_token_rejects_garbage():
    assert decode_access_token("not.a.real.token") is None


def test_decode_access_token_rejects_a_token_signed_with_the_wrong_secret():
    # A token that's well-formed but wasn't issued by this app -- the
    # signature check (not just shape) must be what rejects it.
    forged = jwt.encode(
        {"sub": "someone", "role": "student", "exp": time.time() + 3600},
        "a-different-secret-entirely",
        algorithm=settings.jwt_algorithm,
    )
    assert decode_access_token(forged) is None


def test_decode_access_token_rejects_an_expired_token():
    expired = jwt.encode(
        {"sub": "someone", "role": "student", "exp": time.time() - 10},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    assert decode_access_token(expired) is None


def test_create_access_token_sets_expiry_in_the_future_by_jwt_expire_minutes():
    before = time.time()
    token = create_access_token(user_id="someone", role="student")
    payload = decode_access_token(token)
    expected_latest = before + settings.jwt_expire_minutes * 60 + 5  # small slack
    assert payload["exp"] <= expected_latest
    assert payload["exp"] > before


@pytest.mark.parametrize("role", ["student", "teacher", "parent", "admin"])
def test_create_access_token_carries_whatever_role_its_given(role):
    # Not validated against a fixed enum on purpose (ADR-017: "User+role
    # table now" was chosen specifically so other roles can be added
    # later without reworking this). A role column constraint, if one
    # gets added later, belongs at the DB/model layer, not here.
    token = create_access_token(user_id="someone", role=role)
    assert decode_access_token(token)["role"] == role
