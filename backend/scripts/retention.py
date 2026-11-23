"""
deep scan M1: delete what THUTOra no longer needs (POPIA s14). Run nightly,
e.g. from Cloud Scheduler / cron, from backend/:

    python -m scripts.retention            # delete
    python -m scripts.retention --dry-run  # only count

Always cleaned (no personal value once spent):
  rate-limit events older than 2 days; SMS sign-up codes older than 1 day;
  family invites used or expired more than 30 days ago.
Cleaned only when a period is set in .env (0 = keep):
  RETENTION_CONVERSATION_DAYS  tutor conversations (and their uploads)
  RETENTION_UPLOAD_DAYS        uploaded files not used in a conversation
  RETENTION_AUDIT_DAYS         audit trail entries
  RETENTION_SUPPORT_DAYS       resolved support tickets
"""

import argparse
import asyncio
import logging
from datetime import timedelta

from sqlalchemy import delete, func, select, update

from app.core.clock import utcnow_naive
from app.core.config import settings
from app.core.database import async_session_factory
from app.models import (
    Attachment,
    AuditEvent,
    RateEvent,
    SignupCode,
    SupportMessage,
    SupportTicket,
    TutorMessage,
    TutorSession,
    ViewerInvite,
)
from app.services.privacy import remove_files

log = logging.getLogger("thutora.retention")


async def run(dry_run: bool) -> dict:
    now = utcnow_naive()
    counts: dict[str, int] = {}
    files: list[str] = []
    async with async_session_factory() as db:
        async def wipe(label, model, condition):
            if dry_run:
                counts[label] = (await db.execute(select(func.count()).select_from(model).where(condition))).scalar_one()
            else:
                counts[label] = (await db.execute(delete(model).where(condition))).rowcount or 0

        await wipe("rate events", RateEvent, RateEvent.created_at < now - timedelta(days=2))
        await wipe("sign-up codes", SignupCode, SignupCode.created_at < now - timedelta(days=1))
        await wipe(
            "family invites",
            ViewerInvite,
            ((ViewerInvite.used_at.is_not(None)) & (ViewerInvite.used_at < now - timedelta(days=30)))
            | (ViewerInvite.expires_at < now - timedelta(days=30)),
        )

        if settings.retention_conversation_days > 0:
            cutoff = now - timedelta(days=settings.retention_conversation_days)
            old_sessions = (
                await db.execute(select(TutorSession.id).where(TutorSession.created_at < cutoff))
            ).scalars().all()
            # keep a conversation that's still in use: only sessions with no recent message
            active = set(
                (
                    await db.execute(
                        select(TutorMessage.session_id).where(
                            TutorMessage.session_id.in_(old_sessions), TutorMessage.created_at >= cutoff
                        )
                    )
                ).scalars().all()
            ) if old_sessions else set()
            stale = [s for s in old_sessions if s not in active]
            if stale:
                atts = (await db.execute(select(Attachment).where(Attachment.session_id.in_(stale)))).scalars().all()
                files += [a.storage_path for a in atts]
                if not dry_run:
                    await db.execute(update(Attachment).where(Attachment.session_id.in_(stale)).values(message_id=None))
                    await db.execute(delete(Attachment).where(Attachment.session_id.in_(stale)))
                    await db.execute(delete(TutorMessage).where(TutorMessage.session_id.in_(stale)))
                    await db.execute(delete(TutorSession).where(TutorSession.id.in_(stale)))
            counts["conversations"] = len(stale)

        if settings.retention_upload_days > 0:
            cutoff = now - timedelta(days=settings.retention_upload_days)
            loose = (
                await db.execute(select(Attachment).where(Attachment.session_id.is_(None), Attachment.created_at < cutoff))
            ).scalars().all()
            files += [a.storage_path for a in loose]
            if not dry_run and loose:
                await db.execute(delete(Attachment).where(Attachment.id.in_([a.id for a in loose])))
            counts["unused uploads"] = len(loose)

        if settings.retention_support_days > 0:  # ADR-050: resolved tickets only
            cutoff = now - timedelta(days=settings.retention_support_days)
            old = (
                await db.execute(
                    select(SupportTicket.id).where(SupportTicket.status == "resolved", SupportTicket.resolved_at < cutoff)
                )
            ).scalars().all()
            if old and not dry_run:
                await db.execute(delete(SupportMessage).where(SupportMessage.ticket_id.in_(old)))
                await db.execute(delete(SupportTicket).where(SupportTicket.id.in_(old)))
            counts["support tickets"] = len(old)

        if settings.retention_audit_days > 0:
            await wipe("audit entries", AuditEvent, AuditEvent.created_at < now - timedelta(days=settings.retention_audit_days))

        if dry_run:
            await db.rollback()
        else:
            await db.commit()
            remove_files(files)
    counts["files"] = len(files)
    return counts


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()
    result = asyncio.run(run(a.dry_run))
    print(("Would delete: " if a.dry_run else "Deleted: ") + ", ".join(f"{v} {k}" for k, v in result.items()))
