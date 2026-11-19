"""
NEW 19 Nov 2026 (ADR-043, verifying parents -- modelled on how d6 Connect
works in SA schools).

The school is the trust anchor. A parent can connect to a learner in two ways:
 1. School-issued login (ADR-038): staff create it and hand it over.
 2. Self-sign-up: the parent enters their cellphone number; if it matches a
    guardian contact the SCHOOL recorded for a learner, an SMS code proves the
    parent holds that phone, and they're linked to exactly those learners.
    A number the school doesn't have gets nothing (and the reply never says
    whether a number is on file).
Viewers (grandparents, carers) are invited by a linked guardian with a one-time
invite code; the guardian or the school can remove them.

Pure helpers here; endpoints in app/routers/family.py.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets

from app.core.config import settings

OTP_MINUTES = 10
OTP_MAX_ATTEMPTS = 5
INVITE_DAYS = 7
_INVITE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O, 1/I


def normalize_sa_cellphone(raw: str) -> str:
    """'082 123 4567', '+27 82 123 4567', '27821234567' -> '+27821234567'."""
    digits = re.sub(r"[^\d+]", "", raw or "")
    if digits.startswith("+27"):
        rest = digits[3:]
    elif digits.startswith("0027"):
        rest = digits[4:]
    elif digits.startswith("27") and len(digits) == 11:
        rest = digits[2:]
    elif digits.startswith("0"):
        rest = digits[1:]
    else:
        raise ValueError("Enter a South African cellphone number, e.g. 082 123 4567")
    if not re.fullmatch(r"[6-8]\d{8}", rest):
        raise ValueError("Enter a South African cellphone number, e.g. 082 123 4567")
    return "+27" + rest


def local_format(e164: str) -> str:
    """'+27821234567' -> '0821234567' (what a parent types to log in)."""
    return "0" + e164[3:]


def mask_cellphone(e164: str | None) -> str | None:
    if not e164:
        return None
    local = local_format(e164)
    return f"{local[:3]} *** {local[-4:]}"


def _hash(value: str) -> str:
    return hmac.new(settings.jwt_secret_key.encode(), value.encode(), hashlib.sha256).hexdigest()


def new_otp() -> tuple[str, str]:
    code = f"{secrets.randbelow(1_000_000):06d}"
    return code, _hash(code)


def otp_matches(code: str, code_hash: str) -> bool:
    return hmac.compare_digest(_hash((code or "").strip()), code_hash)


def new_invite_code() -> tuple[str, str]:
    raw = "".join(secrets.choice(_INVITE_ALPHABET) for _ in range(8))
    return f"{raw[:4]}-{raw[4:]}", _hash(raw)


def invite_hash(typed: str) -> str:
    return _hash(re.sub(r"[^A-Za-z0-9]", "", typed or "").upper())
