"""ADR-051: authenticator codes match the standard (RFC 6238 test vectors)."""

import base64

from app.services import totp

RFC_SECRET = base64.b32encode(b"12345678901234567890").decode().rstrip("=")


def test_rfc6238_vectors_six_digits():
    # RFC 6238 Appendix B (SHA-1): 94287082 at T=59 -> last 6 digits
    assert totp.code_at(RFC_SECRET, 59 // 30) == "287082"
    assert totp.code_at(RFC_SECRET, 1111111109 // 30) == "081804"
    assert totp.code_at(RFC_SECRET, 2000000000 // 30) == "279037"


def test_one_step_of_clock_drift_is_allowed_but_not_two():
    s = totp.new_secret()
    now = 1_800_000_000
    step = totp.current_step(now)
    assert totp.match_step(s, totp.code_at(s, step), now) == step
    assert totp.match_step(s, totp.code_at(s, step - 1), now) == step - 1
    assert totp.match_step(s, totp.code_at(s, step + 2), now) is None
    assert totp.match_step(s, "12345", now) is None and totp.match_step(s, "abcdef", now) is None


def test_setup_uri_names_the_console():
    uri = totp.otpauth_uri("ABC", "siya@zynoratech.co.za")
    assert uri.startswith("otpauth://totp/THUTOra%20Console%3Asiya%40zynoratech.co.za?secret=ABC")
