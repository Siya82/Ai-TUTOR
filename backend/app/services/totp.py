"""
NEW 23 Nov 2026 (ADR-051). Authenticator-app codes (TOTP, RFC 6238) for the
THUTOra Console's second sign-in step. Standard settings -- SHA-1, 6 digits,
30 seconds -- so Google Authenticator, Microsoft Authenticator and others all
work. No library and no SMS provider needed.
"""

import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote

STEP = 30
DIGITS = 6
ISSUER = "THUTOra Console"


def new_secret() -> str:
    """160 random bits, base32 without padding (what authenticator apps expect)."""
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def _key(secret: str) -> bytes:
    s = secret.strip().replace(" ", "").upper()
    return base64.b32decode(s + "=" * (-len(s) % 8))


def code_at(secret: str, step: int) -> str:
    digest = hmac.new(_key(secret), struct.pack(">Q", step), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(value % 10**DIGITS).zfill(DIGITS)


def current_step(now: float | None = None) -> int:
    return int((time.time() if now is None else now) // STEP)


def match_step(secret: str, code: str, now: float | None = None, window: int = 1) -> int | None:
    """The time step the code belongs to (allowing one step of clock drift
    either way), or None. The caller stores the step so a code can't be
    used twice."""
    code = (code or "").strip().replace(" ", "")
    if not (code.isdigit() and len(code) == DIGITS):
        return None
    step = current_step(now)
    for s in range(step - window, step + window + 1):
        if hmac.compare_digest(code_at(secret, s), code):
            return s
    return None


def otpauth_uri(secret: str, email: str) -> str:
    """What the QR code holds; scanning it adds the account to the app."""
    label = quote(f"{ISSUER}:{email}")
    return f"otpauth://totp/{label}?secret={secret}&issuer={quote(ISSUER)}&digits={DIGITS}&period={STEP}"
