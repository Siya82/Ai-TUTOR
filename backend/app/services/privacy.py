"""
NEW 19 Nov 2026 (ADR-037, POPIA basics).

- PRIVACY_NOTICE_VERSION: the version of the privacy notice shown in the app
  (frontend/src/components/PrivacyNotice.jsx). Consent records note which
  version the parent agreed to; bump this when the notice text changes.
- export_learner_data(): everything THUTOra holds about one learner, as
  plain JSON -- for a parent's access request (POPIA s23).
- delete_learner_data(): removes the learner and every record tied to them,
  including uploaded files -- for a deletion request (POPIA s24) or a
  learner who leaves and whose data isn't needed any more.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AssignmentTarget,
    Attachment,
    Attempt,
    ClassMember,
    ConsentRecord,
    Learner,
    LearnerGuardian,
    ParentLink,
    ViewerInvite,
    PracticalRun,
    Question,
    Topic,
    TutorMessage,
    TutorSession,
    User,
)

PRIVACY_NOTICE_VERSION = "2026-11-19"
log = logging.getLogger("thutora.privacy")


def _iso(dt):
    return dt.isoformat() if dt else None


async def export_learner_data(db: AsyncSession, learner: Learner) -> dict:
    user = await db.get(User, learner.user_id) if learner.user_id else None
    sessions = (
        await db.execute(
            select(TutorSession, Topic.name)
            .join(Topic, TutorSession.topic_id == Topic.id)
            .where(TutorSession.learner_id == learner.id)
            .order_by(TutorSession.created_at)
        )
    ).all()
    session_ids = [s.id for s, _ in sessions]
    messages = []
    if session_ids:
        messages = (
            await db.execute(
                select(TutorMessage)
                .where(TutorMessage.session_id.in_(session_ids))
                .order_by(TutorMessage.created_at)
            )
        ).scalars().all()
    by_session: dict = {}
    for m in messages:
        by_session.setdefault(m.session_id, []).append(
            {"role": m.role, "content": m.content, "at": _iso(m.created_at)}
        )
    attempts = (
        await db.execute(
            select(Attempt, Question.text)
            .join(Question, Attempt.question_id == Question.id)
            .where(Attempt.learner_id == learner.id)
            .order_by(Attempt.created_at)
        )
    ).all()
    attachments = (
        await db.execute(select(Attachment).where(Attachment.learner_id == learner.id))
    ).scalars().all()
    consents = (
        await db.execute(select(ConsentRecord).where(ConsentRecord.learner_id == learner.id))
    ).scalars().all()
    return {
        "exported_at_notice_version": PRIVACY_NOTICE_VERSION,
        "learner": {
            "name": learner.display_name,
            "grade": learner.grade,
            "student_number": user.student_number if user else None,
            "home_language": learner.home_language,
            "preferred_modality": learner.preferred_modality,
            "created_at": _iso(learner.created_at),
            "account_active": bool(user.is_active) if user else None,
        },
        "tutor_conversations": [
            {"topic": topic_name, "started": _iso(s.created_at), "messages": by_session.get(s.id, [])}
            for s, topic_name in sessions
        ],
        "answers": [
            {
                "question": q_text,
                "answer": a.learner_response,
                "correct": a.is_correct,
                "feedback": a.ai_feedback,
                "at": _iso(a.created_at),
            }
            for a, q_text in attempts
        ],
        "uploaded_files": [
            {"file_name": a.original_filename, "type": a.kind, "uploaded": _iso(a.created_at)}
            for a in attachments
        ],
        "consent_records": [
            {
                "given_by": c.given_by_name,
                "relationship": c.relationship_to_learner,
                "method": c.method,
                "notice_version": c.notice_version,
                "recorded": _iso(c.recorded_at),
                "withdrawn": _iso(c.withdrawn_at),
            }
            for c in consents
        ],
    }


def _remove_file(path: str) -> None:
    try:
        p = Path(path)
        if p.is_file():
            p.unlink()
        parent = p.parent
        if parent.is_dir() and not any(parent.iterdir()):
            shutil.rmtree(parent, ignore_errors=True)
    except OSError as exc:  # a missing file shouldn't stop the deletion
        log.warning("Couldn't remove attachment file %s: %s", path, exc)


async def delete_learner_data(db: AsyncSession, learner: Learner) -> tuple[dict, list[str]]:
    """
    Deletes (does not commit) the learner, their login and all their
    records. Returns (counts, file paths): the caller removes the files with
    remove_files() only AFTER the commit succeeds, so a failed commit never
    leaves database rows pointing at deleted files.
    """
    lid = learner.id
    attachments = (await db.execute(select(Attachment).where(Attachment.learner_id == lid))).scalars().all()
    paths = [a.storage_path for a in attachments]
    session_ids = (
        await db.execute(select(TutorSession.id).where(TutorSession.learner_id == lid))
    ).scalars().all()

    counts = {"attachments": len(attachments), "conversations": len(session_ids)}
    await db.execute(delete(Attachment).where(Attachment.learner_id == lid))
    if session_ids:
        await db.execute(delete(TutorMessage).where(TutorMessage.session_id.in_(session_ids)))
        await db.execute(delete(TutorSession).where(TutorSession.id.in_(session_ids)))
    counts["answers"] = (await db.execute(delete(Attempt).where(Attempt.learner_id == lid))).rowcount or 0
    await db.execute(delete(AssignmentTarget).where(AssignmentTarget.learner_id == lid))
    await db.execute(delete(ClassMember).where(ClassMember.learner_id == lid))
    await db.execute(delete(PracticalRun).where(PracticalRun.learner_id == lid))
    await db.execute(delete(ConsentRecord).where(ConsentRecord.learner_id == lid))
    await db.execute(delete(ParentLink).where(ParentLink.learner_id == lid))  # ADR-038
    await db.execute(delete(LearnerGuardian).where(LearnerGuardian.learner_id == lid))  # ADR-043
    await db.execute(delete(ViewerInvite).where(ViewerInvite.learner_id == lid))  # ADR-043
    user_id = learner.user_id
    await db.delete(learner)
    await db.flush()
    if user_id:
        user = await db.get(User, user_id)
        if user is not None:
            await db.delete(user)
    return counts, paths


def remove_files(paths: list[str]) -> None:
    for path in paths:
        _remove_file(path)
