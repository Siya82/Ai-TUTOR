"""
NEW 20 Nov 2026 (deep scan H4). Production safety checks and structured logs.

check_production_settings() stops the API from starting in production with a
setting that would be unsafe there -- better a failed deploy than a live
service with a weak signing key or a development SMS provider.
"""

import json
import logging
import sys


class UnsafeProductionSettings(RuntimeError):
    pass


def problems(settings) -> list[str]:
    """Unsafe settings for production (empty list = fine). Pure, so it's unit-tested."""
    if settings.environment.lower() not in ("production", "prod"):
        return []
    out = []
    if len(settings.jwt_secret_key or "") < 32 or settings.jwt_secret_key.lower() in ("secret", "changeme", "change-me"):
        out.append("JWT_SECRET_KEY must be a random value of at least 32 characters")
    if any("localhost" in o or "127.0.0.1" in o for o in settings.cors_origins):
        out.append("CORS_ORIGINS must list only the real frontend address(es), not localhost")
    if any(o.startswith("http://") for o in settings.cors_origins):
        out.append("CORS_ORIGINS must use https://")
    if (settings.sms_provider or "").lower() == "console":
        out.append("SMS_PROVIDER=console writes codes to the log; use a real provider or leave it empty")
    if not settings.anthropic_api_key:
        out.append("ANTHROPIC_API_KEY is missing")
    return out


def check_production_settings(settings) -> None:
    found = problems(settings)
    if found:
        raise UnsafeProductionSettings("Refusing to start in production:\n  - " + "\n  - ".join(found))


class _JsonFormatter(logging.Formatter):
    """One JSON object per line: Cloud Logging reads `severity` and `message`,
    and Error Reporting picks up stack traces from `message`."""

    def format(self, record: logging.LogRecord) -> str:
        entry = {"severity": record.levelname, "logger": record.name, "message": record.getMessage()}
        if record.exc_info:
            entry["message"] += "\n" + self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False)


def configure_json_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(logging.INFO)
