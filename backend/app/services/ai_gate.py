"""
NEW 20 Nov 2026 (deep scan M1, H5). May THIS learner's work go to the AI
right now? Two school switches decide, both off by default:

- require_consent: the school only lets learners with a recorded (and not
  withdrawn) parent/guardian consent use AI features (POPIA s35: a child's
  personal information, processed with a competent person's consent).
- ai_budget_usd_month: once the school's AI spend this month reaches its
  budget, AI features pause until the 1st.

Returns None when allowed, or a plain-language reason when not.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ConsentRecord, School
from app.services.ai_cost import school_month

NO_CONSENT = (
    "Your school needs a signed consent form from your parent or guardian before you can use "
    "THUTOra's AI tutor. Please ask your teacher about it."
)
NO_BUDGET = (
    "Your school's THUTOra AI allowance for this month has been used up. It starts again on the 1st -- "
    "you can still read your textbook and do your assignments."
)


async def ai_blocked_reason(db: AsyncSession, school_id: uuid.UUID, learner_id: uuid.UUID | None) -> str | None:
    school = await db.get(School, school_id)
    if school is None:
        return None
    if school.require_consent and learner_id is not None:
        has = (
            await db.execute(
                select(ConsentRecord.id).where(
                    ConsentRecord.learner_id == learner_id, ConsentRecord.withdrawn_at.is_(None)
                ).limit(1)
            )
        ).first()
        if not has:
            return NO_CONSENT
    if school.ai_budget_usd_month is not None:
        spent = (await school_month(db, school_id))["cost_usd"]
        if spent >= float(school.ai_budget_usd_month):
            return NO_BUDGET
    return None
