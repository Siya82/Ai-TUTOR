"""
NEW 23 Nov 2026 (ADR-051). Zynora's onboarding steps, shared by the THUTOra
Console and the command-line scripts (provision_school, manage_registrations,
manage_insights), so both do exactly the same thing.

Nothing here commits: the caller commits, together with its audit line.
"""

import uuid

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utcnow_naive
from app.models import Circuit, District, OfficialAssignment, School, SchoolRegistration, StaffRole, User
from app.services.auth import _generate_unique_login_number, generate_temp_password, hash_password, provision_teacher

FIRST_LOGIN_ROLES = ("principal", "school_admin")


class OnboardingError(ValueError):
    """A plain-language reason the step can't be done (shown to the person)."""


async def add_first_login(
    db: AsyncSession, school: School, display_name: str, role: str = "principal", staff_number: str | None = None
) -> tuple[User, str]:
    """A new staff login with a management role. Returns (user, one-time password)."""
    if role not in FIRST_LOGIN_ROLES:
        raise OnboardingError("Zynora can only create a principal or a school admin.")
    name = (display_name or "").strip()
    if not name:
        raise OnboardingError("Give the person's name.")
    if staff_number:
        staff_number = staff_number.strip()
        clash = (
            await db.execute(select(User.id).where(User.school_id == school.id, User.student_number == staff_number))
        ).first()
        if clash:
            raise OnboardingError(f"Staff number {staff_number} is already used at {school.name}.")
    user, temp = await provision_teacher(db, school=school, staff_number=staff_number or None)
    user.display_name = name
    db.add(StaffRole(user_id=user.id, school_id=school.id, role=role))
    await db.flush()
    return user, temp


async def create_school(
    db: AsyncSession,
    *,
    name: str,
    emis_number: str | None = None,
    province: str | None = None,
    email: str | None = None,
) -> School:
    name = (name or "").strip()
    if not name:
        raise OnboardingError("Give the school's name.")
    school = School(name=name, emis_number=(emis_number or None), province=(province or None), email=(email or None))
    db.add(school)
    await db.flush()
    return school


async def approve_registration(
    db: AsyncSession, reg: SchoolRegistration, as_role: str = "principal", staff_number: str | None = None
) -> tuple[School, User, str]:
    if reg.status != "pending":
        raise OnboardingError(f"This request is already {reg.status}.")
    school = await create_school(
        db, name=reg.school_name, emis_number=reg.emis_number, province=reg.province, email=reg.contact_email
    )
    user, temp = await add_first_login(db, school, reg.contact_name, as_role, staff_number)
    reg.status = "approved"
    reg.school_id = school.id
    reg.decided_at = utcnow_naive()
    return school, user, temp


def reject_registration(reg: SchoolRegistration) -> None:
    if reg.status != "pending":
        raise OnboardingError(f"This request is already {reg.status}.")
    reg.status = "rejected"
    reg.decided_at = utcnow_naive()


def office_name_for(level: Circuit | District) -> str:
    word = "Circuit" if isinstance(level, Circuit) else "District"
    base = level.name if level.name.lower().endswith(word.lower()) else f"{level.name} {word}"
    return f"{base} Office"


async def add_official(
    db: AsyncSession, name: str, *, circuit: Circuit | None = None, district: District | None = None
) -> tuple[User, School, str]:
    """An education official for one circuit or district (ADR-039). Returns
    (user, the office they log in under, one-time password)."""
    if bool(circuit) == bool(district):
        raise OnboardingError("Choose exactly one circuit or district.")
    name = (name or "").strip()
    if not name:
        raise OnboardingError("Give the official's name.")
    level = circuit or district
    office_name = office_name_for(level)
    office = (
        await db.execute(select(School).where(School.name == office_name, School.kind == "office"))
    ).scalar_one_or_none()
    if office is None:
        office = School(name=office_name, kind="office")
        db.add(office)
        await db.flush()
    temp = generate_temp_password()
    user = User(
        role="official",
        school_id=office.id,
        student_number=await _generate_unique_login_number(db, office),
        display_name=name,
        password_hash=hash_password(temp),
        must_change_password=True,
    )
    db.add(user)
    await db.flush()
    db.add(OfficialAssignment(user_id=user.id, circuit_id=circuit.id if circuit else None,
                              district_id=district.id if district else None))
    await db.flush()
    return user, office, temp


async def remove_official(db: AsyncSession, user: User) -> None:
    """Ends an official's access: their area is removed and the login is
    switched off (any open session ends at once)."""
    if user.role != "official":
        raise OnboardingError("That login isn't an education official.")
    await db.execute(delete(OfficialAssignment).where(OfficialAssignment.user_id == user.id))
    user.is_active = False
    user.token_version = (user.token_version or 0) + 1


async def remove_principal_role(db: AsyncSession, role: StaffRole, switch_off: bool) -> User:
    if role.role != "principal":
        raise OnboardingError("Zynora only removes the principal role; the school manages its other roles.")
    user = await db.get(User, role.user_id)
    await db.delete(role)
    if switch_off and user is not None:
        user.is_active = False
        user.token_version = (user.token_version or 0) + 1
    return user


async def give_principal_role(db: AsyncSession, school: School, user_id: uuid.UUID) -> User:
    user = await db.get(User, user_id)
    if user is None or user.school_id != school.id or user.role != "teacher" or not user.is_active:
        raise OnboardingError("That person isn't an active staff member at this school.")
    has = (
        await db.execute(select(StaffRole.id).where(StaffRole.user_id == user.id, StaffRole.role == "principal"))
    ).first()
    if has:
        raise OnboardingError(f"{user.display_name or user.student_number} is already a principal.")
    db.add(StaffRole(user_id=user.id, school_id=school.id, role="principal"))
    await db.flush()
    return user


def http_error(err: OnboardingError) -> HTTPException:
    return HTTPException(status_code=400, detail=str(err))
