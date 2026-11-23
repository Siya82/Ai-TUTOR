"""
Zynora onboarding for INSIGHTS (ADR-039). NEW 19 Nov 2026.

The department structure and officials' access come from an agreement with
the department, not from inside the app, so they're set up with this script
(like scripts/provision_school.py for a school's first principal).

Usage (from backend/):
    python -m scripts.manage_insights add-district --name "Umgungundlovu" --province "KwaZulu-Natal"
    python -m scripts.manage_insights add-circuit --district "Umgungundlovu" --name "Pietermaritzburg North"
    python -m scripts.manage_insights assign-school --school "Imbali Secondary School" --circuit "Pietermaritzburg North"
    python -m scripts.manage_insights add-official --name "Mr T. Mkhize" --circuit "Pietermaritzburg North"
    python -m scripts.manage_insights add-official --name "Dr A. Naidoo" --district "Umgungundlovu"
    python -m scripts.manage_insights list

add-official creates (or reuses) the "<circuit/district> Office" entry that
officials pick on the login screen, and prints the login number and a
one-time password once.
"""

import argparse
import asyncio

from sqlalchemy import select

from app.core.database import async_session_factory
from app.models import Circuit, District, School
from app.services.onboarding import add_official


async def _one(session, model, name, label):
    rows = (await session.execute(select(model).where(model.name == name))).scalars().all()
    if not rows:
        raise SystemExit(f"No {label} called {name!r}")
    if len(rows) > 1:
        raise SystemExit(f"More than one {label} called {name!r}; rename one first")
    return rows[0]


async def main(args) -> None:
    async with async_session_factory() as session:
        if args.cmd == "add-district":
            d = District(name=args.name.strip(), province=args.province.strip())
            session.add(d)
            await session.commit()
            print(f"District {d.name} ({d.province}) created.")
        elif args.cmd == "add-circuit":
            d = await _one(session, District, args.district, "district")
            c = Circuit(district_id=d.id, name=args.name.strip())
            session.add(c)
            await session.commit()
            print(f"Circuit {c.name} created in {d.name}.")
        elif args.cmd == "assign-school":
            s = await _one(session, School, args.school, "school")
            c = await _one(session, Circuit, args.circuit, "circuit")
            s.circuit_id = c.id
            await session.commit()
            print(f"{s.name} is now in circuit {c.name}.")
        elif args.cmd == "add-official":
            if bool(args.circuit) == bool(args.district):
                raise SystemExit("Give exactly one of --circuit or --district")
            circuit = await _one(session, Circuit, args.circuit, "circuit") if args.circuit else None
            district = await _one(session, District, args.district, "district") if args.district else None
            user, office, temp = await add_official(session, args.name, circuit=circuit, district=district)
            office_name = office.name
            await session.commit()
            print(f"Official {user.display_name} created.")
            print(f"  Log in by choosing:  {office_name}")
            print(f"  Login number:        {user.student_number}")
            print(f"  One-time password:   {temp}   (shown once; they choose their own at first login)")
        elif args.cmd == "list":
            for d in (await session.execute(select(District).order_by(District.name))).scalars():
                print(f"{d.name} ({d.province})")
                for c in (
                    await session.execute(select(Circuit).where(Circuit.district_id == d.id).order_by(Circuit.name))
                ).scalars():
                    schools = (
                        await session.execute(select(School.name).where(School.circuit_id == c.id).order_by(School.name))
                    ).scalars().all()
                    print(f"  {c.name}: {', '.join(schools) or '(no schools)'}")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add-district")
    a.add_argument("--name", required=True)
    a.add_argument("--province", required=True)
    a = sub.add_parser("add-circuit")
    a.add_argument("--district", required=True)
    a.add_argument("--name", required=True)
    a = sub.add_parser("assign-school")
    a.add_argument("--school", required=True)
    a.add_argument("--circuit", required=True)
    a = sub.add_parser("add-official")
    a.add_argument("--name", required=True)
    a.add_argument("--circuit")
    a.add_argument("--district")
    sub.add_parser("list")
    asyncio.run(main(p.parse_args()))
