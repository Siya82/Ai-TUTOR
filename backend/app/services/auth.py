"""
Password hashing, JWT issue/verify, and student provisioning.
See docs/ADR-017-student-login.md.

Split the same way every other service module in this app is: pure,
DB-free helpers (hashing, token encode/decode, number generation) are
unit-testable with no database, and the one function that does touch
the database (provision_student) is kept separate and small.
"""

import secrets
import string
from datetime import datetime, timedelta
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import Learner, School, User

# bcrypt pinned to 4.0.1 in requirements.txt specifically because passlib
# 1.7.4 breaks against bcrypt 5.x's removed __about__.__version__ attribute
# -- flagged there before this file existed, so the fix landed with the
# matching pin rather than a mismatched one.
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(raw_password: str) -> str:
    return _pwd_context.hash(raw_password)


def verify_password(raw_password: str, password_hash: str) -> bool:
    return _pwd_context.verify(raw_password, password_hash)


def generate_temp_password(length: int = 10) -> str:
    """
    A random temporary password for a newly provisioned student, handed
    to them out-of-band exactly once (ADR-017) -- never logged, stored
    in plaintext, or re-displayed after the provisioning call returns.
    """
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def generate_student_number(length: int = 6) -> str:
    """
    A system-issued student number, used when a school doesn't supply
    its own (ADR-017). Digits only, so it reads like a real student
    number rather than an obviously-generated code.
    """
    return "".join(secrets.choice(string.digits) for _ in range(length))


def create_access_token(user_id: str, role: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": user_id, "role": role, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any] | None:
    """Returns the decoded payload, or None on any decode/verification failure
    (bad signature, malformed token, or expired -- python-jose checks `exp`
    itself and raises JWTError, which we fold into the same "invalid" result
    rather than distinguishing -- a login boundary shouldn't say more than it
    has to about why a token was rejected)."""
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None


async def provision_student(
    db: AsyncSession,
    *,
    school: School,
    display_name: str,
    grade: int,
    student_number: str | None = None,
    raw_password: str | None = None,
    existing_learner: Learner | None = None,
) -> tuple[User, Learner, str | None]:
    """
    Creates a User (role="student") for one school, and links it to a
    Learner -- a NEW one by default, or `existing_learner` when given
    (used by scripts/seed_dev_data.py to attach a login to the
    already-seeded dev Learner rather than creating a second,
    duplicate one). Returns (user, learner, temp_password).

    temp_password is the plaintext password ONLY when the caller didn't
    supply one -- it must be handed to the student out-of-band, since
    this is the only point it ever exists outside the student's own
    head. It's None when raw_password was given explicitly (the caller
    already knows it in that case).

    student_number is generated and checked against this school's own
    (school_id, student_number) uniqueness constraint with a short
    retry loop if not supplied -- a real collision is rare with a
    6-digit space, but cheap insurance against a one-in-a-million clash
    beats a crash.
    """
    temp_password = None
    if raw_password is None:
        temp_password = generate_temp_password()
        raw_password = temp_password

    if student_number is None:
        for _ in range(10):
            candidate = generate_student_number()
            existing = await db.execute(
                select(User).where(
                    User.school_id == school.id, User.student_number == candidate
                )
            )
            if existing.scalar_one_or_none() is None:
                student_number = candidate
                break
        else:
            raise RuntimeError("Could not generate a unique student number after 10 attempts")

    user = User(
        role="student",
        school_id=school.id,
        student_number=student_number,
        password_hash=hash_password(raw_password),
        must_change_password=temp_password is not None,
    )
    db.add(user)
    await db.flush()  # need user.id for the Learner FK below

    if existing_learner is not None:
        existing_learner.user_id = user.id
        learner = existing_learner
    else:
        learner = Learner(display_name=display_name, grade=grade, user_id=user.id)
        db.add(learner)
    await db.flush()

    return user, learner, temp_password
