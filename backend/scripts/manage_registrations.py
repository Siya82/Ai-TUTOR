"""
Zynora onboarding from the public "Register your school" form (ADR-044).

Approving a request is the same step as scripts/provision_school.py: it
creates the school (with the profile details from the form) and the first
login for the contact person. Do it only after confirming the school --
e.g. phone the school on its official number and check the EMIS number.

Usage (from backend/):
    python -m scripts.manage_registrations list
    python -m scripts.manage_registrations show  <reference>
    python -m scripts.manage_registrations approve <reference> [--as principal|school_admin] [--staff-number P1001]
    python -m scripts.manage_registrations reject  <reference>

<reference> is the 8-character code the form showed (the start of the id).
"""

import argparse
import asyncio

from sqlalchemy import cast, select, String

from app.core.clock import utcnow_naive
from app.core.database import async_session_factory
from app.models import School, SchoolRegistration, StaffRole
from app.services.auth import provision_teacher


async def _find(session, ref: str) -> SchoolRegistration:
    rows = (
        await session.execute(
            select(SchoolRegistration).where(cast(SchoolRegistration.id, String).ilike(f"{ref.strip().lower()}%"))
        )
    ).scalars().all()
    if len(rows) != 1:
        raise SystemExit(f"{len(rows)} requests match {ref!r} -- give more of the id")
    return rows[0]


def _describe(r: SchoolRegistration) -> str:
    return (
        f"{str(r.id)[:8].upper()}  [{r.status}]  {r.school_name} ({r.province}; EMIS {r.emis_number or '-'})\n"
        f"    contact: {r.contact_name}, {r.contact_role}, {r.contact_cellphone}, {r.contact_email or '-'}\n"
        f"    learners: {r.learner_estimate or '-'}   received: {r.created_at:%Y-%m-%d %H:%M}"
        + (f"\n    message: {r.message}" if r.message else "")
    )


async def main(args) -> None:
    async with async_session_factory() as session:
        if args.cmd == "list":
            rows = (
                await session.execute(select(SchoolRegistration).order_by(SchoolRegistration.created_at.desc()))
            ).scalars().all()
            print("\n".join(_describe(r) for r in rows) or "No registration requests.")
            return
        reg = await _find(session, args.ref)
        if args.cmd == "show":
            print(_describe(reg))
            return
        if reg.status != "pending":
            raise SystemExit(f"This request is already {reg.status}.")
        if args.cmd == "reject":
            reg.status = "rejected"
            reg.decided_at = utcnow_naive()
            await session.commit()
            print(f"Rejected {reg.school_name}. Let {reg.contact_name} know on {reg.contact_cellphone}.")
            return

        school = School(
            name=reg.school_name,
            emis_number=reg.emis_number,
            province=reg.province,
            phone=None,
            email=reg.contact_email,
        )
        session.add(school)
        await session.flush()
        user, temp_password = await provision_teacher(session, school=school, staff_number=args.staff_number)
        user.display_name = reg.contact_name
        session.add(StaffRole(user_id=user.id, school_id=school.id, role=args.as_role))
        reg.status = "approved"
        reg.school_id = school.id
        reg.decided_at = utcnow_naive()
        await session.commit()
        print(f"School:         {school.name}  (id {school.id})")
        print(f"First login:    {user.display_name} as {args.as_role}")
        print(f"Staff number:   {user.student_number}")
        print(f"Temp password:  {temp_password}   <- shown once; must be changed at first login")
        if args.as_role != "principal":
            print("Note: a school admin can't grant roles. Add the principal later with scripts/provision_school.py.")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Review 'Register your school' requests (ADR-044).")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    for name in ("show", "reject"):
        sub.add_parser(name).add_argument("ref")
    a = sub.add_parser("approve")
    a.add_argument("ref")
    a.add_argument("--as", dest="as_role", choices=["principal", "school_admin"], default="principal")
    a.add_argument("--staff-number")
    asyncio.run(main(p.parse_args()))
