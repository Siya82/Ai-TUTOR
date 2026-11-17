"""
NEW 17 Nov 2026 (code review #17). datetime.utcnow() is deprecated. Every
timestamp column in this schema is naive UTC (TIMESTAMP WITHOUT TIME ZONE),
so this returns the same value, built the non-deprecated way.
"""

from datetime import datetime, timezone


def utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)
