"""
Slows down password guessing without letting one learner lock out another.

REWRITTEN 20 Nov 2026 (deep scan M2, L6). Before, 5 wrong passwords locked a
login for everyone for 15 minutes -- and learners know each other's student
numbers, so a classmate could lock someone out on purpose. Now:

- PER DEVICE: 5 wrong passwords for a login from one device (the browser's
  own random id) lock that login ON THAT DEVICE for 15 minutes. A classmate
  on their own phone only locks their own phone.
- PER LOGIN, ALL DEVICES: 30 wrong passwords in an hour lock the login
  everywhere for 15 minutes. Far too few to guess an 8+ character password,
  and too many for a prank; it's logged so the school can see it.
- PER NETWORK: 300 failures in 15 minutes from one IP (a whole school can sit
  behind one address, so this is deliberately high).

Counted in the database (rate_limit.py), so it holds across servers.
"""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.services import rate_limit

DEVICE_MAX, DEVICE_WINDOW = 5, 15 * 60
LOGIN_MAX, LOGIN_WINDOW = 30, 60 * 60
IP_MAX, IP_WINDOW = 300, 15 * 60
LOCK_SECONDS = 15 * 60
log = logging.getLogger("thutora.login")


def _login(school_id, number: str) -> str:
    return f"login:{school_id}:{number.strip().lower()}"


async def retry_after_seconds(db: AsyncSession, school_id, number: str, device: str | None, ip: str | None) -> tuple[int, str]:
    """(seconds to wait, which limit) -- (0, "") when the attempt may go ahead."""
    from app.core.clock import utcnow_naive

    now = utcnow_naive()
    checks = [
        (f"{_login(school_id, number)}:dev:{device or ip or '-'}", DEVICE_MAX, DEVICE_WINDOW, "device"),
        (_login(school_id, number), LOGIN_MAX, LOGIN_WINDOW, "login"),
    ]
    if ip:
        checks.append((f"loginip:{ip}", IP_MAX, IP_WINDOW, "network"))
    for key, limit, window, kind in checks:
        if await rate_limit.count(db, key, window) >= limit:
            oldest = await rate_limit.oldest_in_window(db, key, window)
            # locked until LOCK_SECONDS after the failure that hit the limit
            wait = LOCK_SECONDS - int((now - oldest).total_seconds()) if oldest else LOCK_SECONDS
            return max(wait, 30), kind
    return 0, ""


async def record_failure(db: AsyncSession, school_id, number: str, device: str | None, ip: str | None) -> None:
    await rate_limit.hit(db, f"{_login(school_id, number)}:dev:{device or ip or '-'}")
    await rate_limit.hit(db, _login(school_id, number))
    if ip:
        await rate_limit.hit(db, f"loginip:{ip}")
    if await rate_limit.count(db, _login(school_id, number), LOGIN_WINDOW) + 1 >= LOGIN_MAX:
        log.warning("Login %s locked on all devices after %d failures in an hour", school_id, LOGIN_MAX)


async def record_success(db: AsyncSession, school_id, number: str, device: str | None, ip: str | None) -> None:
    await rate_limit.clear(db, f"{_login(school_id, number)}:dev:{device or ip or '-'}")
