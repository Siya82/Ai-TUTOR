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

ADR-051: the THUTOra Console does the same from Registrations (and logs it);
prefer the Console once it's live.
"""

import argparse
import asyncio

from sqlalchemy import cast, select, String

from app.core.database import async_session_factory
from app.models import SchoolRegistration
from app.services.onboarding import OnboardingError, approve_registration, reject_registration


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
        if args.cmd == "reject":
            try:
                reject_registration(reg)
            except OnboardingError as e:
                raise SystemExit(str(e))
            await session.commit()
            print(f"Rejected {reg.school_name}. Let {reg.contact_name} know on {reg.contact_cellphone}.")
            return

        try:
            school, user, temp_password = await approve_registration(session, reg, args.as_role, args.staff_number)
        except OnboardingError as e:
            raise SystemExit(str(e))
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
