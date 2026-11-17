"""
Login throttling (code review #6, 17 Nov 2026).

Student numbers are easy to guess, so without a limit a password could be
guessed by trying many in a row. After MAX_FAILURES wrong passwords for
the same login (school + number) within WINDOW, that login is locked for
LOCKOUT; separately, one IP address gets at most MAX_IP_FAILURES failures
per WINDOW across all logins (a whole class behind one school router
shares an IP, hence the higher number). A successful login clears that
login's count.

Kept in memory: simple, no new dependency, and fine for one server. With
several servers (e.g. Cloud Run scaling out) each keeps its own count, so
the limits are per server -- move this to the database or Redis then.
"""

import logging
import time
from collections import defaultdict, deque

MAX_FAILURES = 5
MAX_IP_FAILURES = 50
WINDOW_SECONDS = 15 * 60
LOCKOUT_SECONDS = 15 * 60

_failures: dict[str, deque[float]] = defaultdict(deque)
_ip_failures: dict[str, deque[float]] = defaultdict(deque)
_locked_until: dict[str, float] = {}
log = logging.getLogger("thutora.login")


def _key(school_id, number: str) -> str:
    return f"{school_id}:{number.strip().lower()}"


def _prune(q: deque, now: float) -> None:
    while q and now - q[0] > WINDOW_SECONDS:
        q.popleft()


def retry_after_seconds(school_id, number: str, ip: str | None, now: float | None = None) -> int:
    """Seconds until this attempt may be made, or 0 if it may go ahead."""
    now = time.monotonic() if now is None else now
    until = _locked_until.get(_key(school_id, number), 0)
    if until > now:
        return int(until - now) + 1
    if ip:
        q = _ip_failures[ip]
        _prune(q, now)
        if len(q) >= MAX_IP_FAILURES:
            return int(WINDOW_SECONDS - (now - q[0])) + 1
    return 0


def record_failure(school_id, number: str, ip: str | None, now: float | None = None) -> None:
    now = time.monotonic() if now is None else now
    key = _key(school_id, number)
    q = _failures[key]
    _prune(q, now)
    q.append(now)
    if len(q) >= MAX_FAILURES:
        _locked_until[key] = now + LOCKOUT_SECONDS
        q.clear()
        log.warning("Login locked for 15 min after repeated failures (school %s)", school_id)
    if ip:
        _ip_failures[ip].append(now)


def record_success(school_id, number: str) -> None:
    key = _key(school_id, number)
    _failures.pop(key, None)
    _locked_until.pop(key, None)


def reset() -> None:
    """For tests."""
    _failures.clear()
    _ip_failures.clear()
    _locked_until.clear()
