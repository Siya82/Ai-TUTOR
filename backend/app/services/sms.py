"""
NEW 19 Nov 2026 (ADR-043). Sending SMS (parent sign-up codes).

SMS_PROVIDER in backend/.env chooses how:
  ""         -- no SMS: parent self-sign-up is switched off (school-issued
                logins still work). The default outside development.
  "console"  -- development only: the message is written to the backend log
                instead of sent, so sign-up can be tried without a provider.
                Used automatically when ENVIRONMENT=development.
A real provider (e.g. Clickatell, BulkSMS) plugs in as another branch here
once Zynora has an account; nothing else changes.
"""

import logging

from app.core.config import settings

log = logging.getLogger("thutora.sms")


class SmsUnavailable(Exception):
    pass


def provider() -> str:
    chosen = (settings.sms_provider or "").strip().lower()
    if not chosen and settings.environment.lower() in ("development", "dev", "local"):
        return "console"
    if chosen == "console" and settings.environment.lower() not in ("development", "dev", "local"):
        return ""  # never "send" codes to a log in production
    return chosen


def sms_enabled() -> bool:
    return provider() in ("console",)


async def send_sms(to_e164: str, text: str) -> None:
    p = provider()
    if p == "console":
        log.warning("DEV SMS to %s: %s", to_e164, text)
        return
    raise SmsUnavailable("SMS sending isn't set up")
