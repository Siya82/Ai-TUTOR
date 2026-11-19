"""
NEW 19 Nov 2026 (code review 19 Nov #11). One line per sensitive action.

    await audit.record(db, actor_id, school_id, "password.reset", "user", user.id, {...})

Adds the row to the caller's session; the caller's commit saves it with the
change itself, so an action and its audit line succeed or fail together.
Never pass passwords, codes or conversation text in `details`.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditEvent

# Plain-language labels for the ADMIN activity list.
LABELS = {
    "password.reset": "Reset a password",
    "user.deactivate": "Switched off a login",
    "user.reactivate": "Switched a login back on",
    "user.edit": "Changed a person's details",
    "role.grant": "Gave a role",
    "role.revoke": "Removed a role",
    "staff.create": "Created a staff login",
    "consent.record": "Recorded consent",
    "consent.withdraw": "Recorded consent withdrawn",
    "privacy.export": "Downloaded a learner's data",
    "privacy.delete": "Deleted a learner's data",
    "mark.override": "Changed an AI mark",
    "assignment.delete": "Deleted an assignment",
    "school.settings": "Changed school settings",
    "parent.link": "Linked a parent",
    "parent.unlink": "Unlinked a parent",
    "learners.promote": "Promoted learners to the next grade",
}


async def record(
    db: AsyncSession,
    actor_user_id: uuid.UUID | None,
    school_id: uuid.UUID | None,
    action: str,
    target_type: str | None = None,
    target_id: uuid.UUID | str | None = None,
    details: dict | None = None,
) -> None:
    db.add(
        AuditEvent(
            actor_user_id=actor_user_id,
            school_id=school_id,
            action=action,
            target_type=target_type,
            target_id=str(target_id) if target_id is not None else None,
            details=details,
        )
    )
