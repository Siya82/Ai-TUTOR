"""
NEW 23 Nov 2026 (ADR-051). Sign-in for the THUTOra Console (Zynora staff).

Separate from school logins on purpose:
- Console tokens carry aud="thutora-console". The school decoder
  (services/auth.decode_access_token) rejects any token with an audience,
  and the Console decoder requires this one -- so neither kind of token
  opens the other side, even though both are signed with JWT_SECRET_KEY.
- Two steps: email + password gives a 5-minute "mfa" token that can only
  be used to send an authenticator code; the code gives a full token that
  lasts CONSOLE_SESSION_MINUTES (30 by default).
- "ver" in the token is the staff member's token_version, bumped on a
  password change, a 2FA reset or switch-off, so old sessions end at once.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from jwt import PyJWTError

from app.core.config import settings

AUDIENCE = "thutora-console"
MFA_MINUTES = 5
ROLES = ("agent", "lead", "director")
RANK = {r: i for i, r in enumerate(ROLES)}
ROLE_LABEL = {"agent": "Support agent", "lead": "Support lead", "director": "Director"}


def create_console_token(staff_id: str, role: str, version: int, stage: str = "full") -> str:
    minutes = MFA_MINUTES if stage == "mfa" else settings.console_session_minutes
    payload = {
        "sub": staff_id,
        "role": role,
        "ver": version,
        "stage": stage,
        "aud": AUDIENCE,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=minutes),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_console_token(token: str) -> dict[str, Any] | None:
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm], audience=AUDIENCE)
    except PyJWTError:
        return None


def at_least(role: str, minimum: str) -> bool:
    return RANK.get(role, -1) >= RANK[minimum]
