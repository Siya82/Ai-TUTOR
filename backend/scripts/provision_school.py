"""
Zynora onboarding: create a school and its first principal (ADR-031).

NEW 17 Nov 2026. The top of each school's tree can't be approved inside
the app -- it starts with a signed agreement between the school (or its
department) and Zynora. This script is the step that follows that
agreement. After it, the principal grants every other role in the app.

Usage (from backend/):
    python -m scripts.provision_school --school "Imbali Secondary School" --principal "Ms N. Dlamini"
    python -m scripts.provision_school --school-id <uuid> --principal "Mr S. Ndlovu" --staff-number P1001

The principal's temporary password is printed once; they must change it
on first login.
"""

import argparse
import asyncio
import uuid

from sqlalchemy import select

from app.core.database import async_session_factory
from app.models import School, StaffRole, User
from app.services.auth import provision_teacher


async def main(args) -> None:
    async with async_session_factory() as session:
        if args.school_id:
            school = await session.get(School, uuid.UUID(args.school_id))
            if school is None:
                raise SystemExit(f"No school with id {args.school_id}")
        else:
            school = School(name=args.school.strip())
            session.add(school)
            await session.flush()

        if args.staff_number:
            clash = (
                await session.execute(
                    select(User.id).where(User.school_id == school.id, User.student_number == args.staff_number)
                )
            ).first()
            if clash:
                raise SystemExit(f"Staff number {args.staff_number} is already used at {school.name}")

        user, temp_password = await provision_teacher(session, school=school, staff_number=args.staff_number)
        user.display_name = args.principal.strip()
        session.add(StaffRole(user_id=user.id, school_id=school.id, role="principal"))
        await session.commit()

        print(f"School:            {school.name}  (id {school.id})")
        print(f"Principal:         {user.display_name}")
        print(f"Staff number:      {user.student_number}")
        print(f"Temp password:     {temp_password}   <- shown once; must be changed at first login")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create a school and its first principal (ADR-031).")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--school", help="Name of a NEW school to create")
    group.add_argument("--school-id", help="Id of an EXISTING school")
    parser.add_argument("--principal", required=True, help="Principal's display name")
    parser.add_argument("--staff-number", help="Login number (auto-generated if omitted)")
    asyncio.run(main(parser.parse_args()))
