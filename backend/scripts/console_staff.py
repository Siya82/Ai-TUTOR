"""
NEW 23 Nov 2026 (ADR-051). THUTOra Console staff, from the command line.

Use it to create the FIRST director; after that, directors add people in the
Console under Staff. Also the way back in if every director is locked out.
Run from backend/:

    python -m scripts.console_staff create --email siya@zynoratech.co.za --name "Siya Zondi" --role director
    python -m scripts.console_staff list
    python -m scripts.console_staff reset-authenticator --email siya@zynoratech.co.za
    python -m scripts.console_staff reset-password --email siya@zynoratech.co.za
    python -m scripts.console_staff switch-off --email someone@zynoratech.co.za

A new or reset password is printed once; it must be changed at the next
sign-in. The authenticator app is set up at the first sign-in.
"""

import argparse
import asyncio

from sqlalchemy import select

from app.core.database import async_session_factory
from app.models import AuditEvent, ConsoleStaff
from app.services.auth import generate_temp_password, hash_password
from app.services.console_auth import ROLE_LABEL, ROLES


async def _get(db, email: str) -> ConsoleStaff:
    s = (await db.execute(select(ConsoleStaff).where(ConsoleStaff.email == email.strip().lower()))).scalar_one_or_none()
    if s is None:
        raise SystemExit(f"No Console staff with email {email}.")
    return s


def _note(db, staff: ConsoleStaff, action: str) -> None:
    # done from the server, so the person it was done to is recorded as the actor
    db.add(AuditEvent(console_staff_id=staff.id, action=action, target_type="console_staff",
                      target_id=str(staff.id), details={"via": "script"}))


async def main(a) -> None:
    async with async_session_factory() as db:
        if a.cmd == "list":
            rows = (await db.execute(select(ConsoleStaff).order_by(ConsoleStaff.display_name))).scalars().all()
            for s in rows:
                state = "on" if s.is_active else "OFF"
                app = "app set up" if s.totp_confirmed else "no app yet"
                print(f"{s.display_name:<25} {s.email:<35} {ROLE_LABEL[s.role]:<15} {state:<4} {app}")
            if not rows:
                print("No Console staff yet. Create the first director with: create --role director")
            return
        if a.cmd == "create":
            email = a.email.strip().lower()
            if (await db.execute(select(ConsoleStaff.id).where(ConsoleStaff.email == email))).first():
                raise SystemExit("Someone already uses that email.")
            temp = generate_temp_password(14)
            s = ConsoleStaff(email=email, display_name=a.name.strip(), role=a.role, password_hash=hash_password(temp))
            db.add(s)
            await db.flush()
            _note(db, s, "console_staff.create")
            await db.commit()
            print(f"Created {s.display_name} ({ROLE_LABEL[s.role]}).")
            print(f"  Email:              {s.email}")
            print(f"  Temporary password: {temp}   <- shown once; change it at first sign-in")
            print("  At first sign-in, scan the QR code with an authenticator app.")
            return
        s = await _get(db, a.email)
        if a.cmd == "reset-authenticator":
            s.totp_secret, s.totp_confirmed, s.totp_last_step = None, False, None
            s.token_version += 1
            _note(db, s, "console_staff.reset_2fa")
            print(f"{s.display_name} will set up the authenticator app again at the next sign-in.")
        elif a.cmd == "reset-password":
            temp = generate_temp_password(14)
            s.password_hash, s.must_change_password = hash_password(temp), True
            s.token_version += 1
            _note(db, s, "console_staff.reset_password")
            print(f"Temporary password for {s.display_name}: {temp}   <- shown once")
        elif a.cmd == "switch-off":
            s.is_active = False
            s.token_version += 1
            _note(db, s, "console_staff.active")
            print(f"{s.display_name} can no longer sign in to the Console.")
        await db.commit()


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("create")
    c.add_argument("--email", required=True)
    c.add_argument("--name", required=True)
    c.add_argument("--role", choices=ROLES, default="agent")
    sub.add_parser("list")
    for name in ("reset-authenticator", "reset-password", "switch-off"):
        sub.add_parser(name).add_argument("--email", required=True)
    asyncio.run(main(p.parse_args()))
