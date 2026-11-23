"""
NEW 23 Nov 2026 (ADR-050). Support tickets: categories, priorities, who may
see a ticket, and email alerts.

Staff (users with role "teacher", which includes principals and school
admins) and district officials may log tickets. Learners and parents are
pointed to their school instead: the school is POPIA's responsible party
and knows the learner; Zynora shouldn't collect children's details through
a help form.
"""

import asyncio
import logging
import re
import smtplib
from email.message import EmailMessage

from app.core.config import settings

log = logging.getLogger("thutora.support")

# category -> (label shown in the form, default priority)
CATEGORIES: dict[str, tuple[str, str]] = {
    "outage": ("THUTOra is down or not loading", "p1"),
    "safeguarding": ("A learner may be at risk", "p1"),
    "data_privacy": ("Data or privacy concern (e.g. information seen by the wrong person)", "p1"),
    "account": ("Logins, passwords or accounts", "p3"),
    "bug": ("Something isn't working properly", "p3"),
    "content": ("A question, video or textbook page is wrong", "p3"),
    "how_to": ("How do I...?", "p3"),
    "billing": ("Contract, billing or AI budget", "p3"),
    "idea": ("Suggestion or feature request", "p4"),
}
PRIORITY_LABEL = {"p1": "Urgent", "p2": "A class is blocked", "p3": "Normal", "p4": "Suggestion"}
STATUSES = ("open", "waiting_on_school", "resolved")
SUPPORT_ROLES = {"teacher", "official"}


def priority_for(category: str, blocking: bool) -> str:
    """Urgent categories are always p1; a learner-facing blocker is p2."""
    default = CATEGORIES[category][1]
    if default == "p1":
        return "p1"
    return "p2" if blocking else default


def whatsapp_link(number: str) -> str:
    digits = re.sub(r"\D", "", number)
    if digits.startswith("0"):
        digits = "27" + digits[1:]
    return f"https://wa.me/{digits}"


def contact() -> dict:
    return {
        "email": settings.support_email,
        "whatsapp": settings.support_whatsapp,
        "whatsapp_link": whatsapp_link(settings.support_whatsapp) if settings.support_whatsapp else None,
        "hours": settings.support_hours,
    }


def _send(subject: str, body: str, to: str) -> None:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from or settings.smtp_user or settings.support_email
    msg["To"] = to
    msg.set_content(body)
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as s:
        s.starttls()
        if settings.smtp_user:
            s.login(settings.smtp_user, settings.smtp_password)
        s.send_message(msg)


async def alert_zynora(subject: str, body: str, urgent: bool = False) -> None:
    """Tell the support mailbox. Never raises: a mail problem must not lose
    the ticket, which is already saved. Urgent tickets also log at ERROR, so
    Cloud Error Reporting alerts even if email isn't set up."""
    (log.error if urgent else log.warning)("SUPPORT: %s", subject)
    if not settings.smtp_host or not settings.support_email:
        return
    try:
        await asyncio.to_thread(_send, subject, body, settings.support_email)
    except Exception:  # noqa: BLE001 -- logged, ticket already stored
        log.exception("Support email to %s failed", settings.support_email)
