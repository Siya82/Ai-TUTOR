"""
POST /tutor/message -- the real tutor conversation endpoint.

REBUILD NOTE: rebuilt from REBUILD_SPEC.md Section 1 -- not recovered
code. Wires diagnosis.py / personalization.py / tutor_orchestration.py /
tutor.py / math_guard.py (all rebuilt from spec, see each file's own
REBUILD NOTE) into a real endpoint against the recovered 11-table
schema.

FIX 14 Nov 2026 (ADR-017, student login): this endpoint no longer takes
learner_id from the request body at all -- it's resolved from the
Authorization bearer token via app/core/security.py's
get_current_learner. This was REBUILD_SPEC.md Section 2 step 8's
long-deferred gap; it's the real fix, not just documentation of the
caveat.

FIX 14 Nov 2026 (ADR-021, real RAG content grounding): content_chunks
ingestion is no longer purely a placeholder -- scripts/ingest_content.py
can now write real grounding content for a topic (isiZulu/English Home
Language first, see ADR-021), and app/services/retrieval.py can look
it up. This endpoint now calls diagnose_root_gap() once itself, BEFORE
prepare_tutor_turn(), specifically to learn which topic will actually
be taught in time to fetch its grounding text -- tutor_orchestration.py
stays deliberately DB-free (see its own docstring), so this doubled,
cheap, pure-Python diagnosis call lives here instead of threading a DB
session through that module. grounding_text is None whenever a topic
has no real ingested content yet (still true for most topics), in
which case prepare_tutor_turn/build_tutor_system_prompt fall back to
the same "not yet wired" placeholder as before -- no behaviour change
for any topic that hasn't been ingested.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import get_current_learner
from app.models import Attachment, Attempt, Learner, Question, Topic, TutorMessage, TutorSession
from app.schemas.tutor import TutorMessageRequest, TutorMessageResponse
from app.services.attachments import build_attachment_content_blocks, history_summary_for
from app.services.diagnosis import diagnose_root_gap
from app.services.math_guard import verify_tutor_response
from app.services.retrieval import get_grounding_text
from app.services.tutor import TutorClient
from app.services.tutor_orchestration import prepare_tutor_turn

router = APIRouter()

# Constructed once at import time, like the recovered services elsewhere
# in this app construct their dependencies at module scope. The
# AsyncAnthropic constructor does not make a network call, so this is
# safe even before a real ANTHROPIC_API_KEY is filled in -- the key is
# only actually used on the first real /tutor/message call.
_tutor_client = TutorClient()

_MAX_PREREQUISITE_DEPTH = 20  # generous guard against an accidental prerequisite cycle


async def _resolve_prerequisite_chain(db: AsyncSession, topic: Topic) -> list[Topic]:
    """
    Walks Topic.prerequisite_id repeatedly, deepest topic last.

    FIX 12 Nov 2026 (multi-subject support, ADR-013): eager-loads
    Topic.subject via selectinload on every fetch in this walk. Needed
    because tutor_orchestration.build the system prompt now reads
    recommended_topic.subject.name/.grade to introduce the tutor
    correctly for whichever subject is actually being taught -- without
    this, that read would trigger an async lazy-load outside any
    greenlet context and raise, not silently return stale data.
    """
    chain = [topic]
    seen = {topic.id}
    current = topic
    for _ in range(_MAX_PREREQUISITE_DEPTH):
        if current.prerequisite_id is None or current.prerequisite_id in seen:
            break
        prereq = await db.get(
            Topic, current.prerequisite_id, options=[selectinload(Topic.subject)]
        )
        if prereq is None:
            break
        chain.append(prereq)
        seen.add(prereq.id)
        current = prereq
    return chain


async def _fetch_scored_attempts_by_topic(
    db: AsyncSession, learner_id: uuid.UUID, topic_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[Attempt]]:
    stmt = (
        select(Attempt, Question.topic_id)
        .join(Question, Attempt.question_id == Question.id)
        .where(Attempt.learner_id == learner_id)
        .where(Question.topic_id.in_(topic_ids))
        .where(Attempt.is_correct.isnot(None))
    )
    result = await db.execute(stmt)
    by_topic: dict[uuid.UUID, list[Attempt]] = {tid: [] for tid in topic_ids}
    for attempt, topic_id in result.all():
        by_topic[topic_id].append(attempt)
    return by_topic


async def _get_or_create_session(
    db: AsyncSession, learner_id: uuid.UUID, topic_id: uuid.UUID
) -> TutorSession:
    stmt = (
        select(TutorSession)
        .where(TutorSession.learner_id == learner_id)
        .where(TutorSession.topic_id == topic_id)
        .order_by(TutorSession.created_at.desc())
    )
    result = await db.execute(stmt)
    existing = result.scalars().first()
    if existing is not None:
        return existing
    session = TutorSession(learner_id=learner_id, topic_id=topic_id)
    db.add(session)
    await db.flush()
    return session


async def _fetch_owned_attachments(
    db: AsyncSession, learner_id: uuid.UUID, attachment_ids: list[uuid.UUID]
) -> list[Attachment]:
    """
    Loads the attachments a student referenced on this turn, filtered by
    learner_id -- now a REAL permission boundary (ADR-017), since
    learner_id itself comes from the authenticated token via
    get_current_learner, not from anything the client can set. Returned
    in the same order as attachment_ids so build_attachment_content_blocks
    presents them to Claude in the order the student attached them.
    """
    if not attachment_ids:
        return []
    stmt = select(Attachment).where(
        Attachment.id.in_(attachment_ids), Attachment.learner_id == learner_id
    )
    result = await db.execute(stmt)
    by_id = {a.id: a for a in result.scalars().all()}
    return [by_id[aid] for aid in attachment_ids if aid in by_id]


def _attachment_to_dict(attachment: Attachment) -> dict:
    return {
        "kind": attachment.kind,
        "storage_path": attachment.storage_path,
        "original_filename": attachment.original_filename,
        "extracted_text": attachment.extracted_text,
        "extraction_warning": attachment.extraction_warning,
    }


@router.post("/message", response_model=TutorMessageResponse)
async def send_tutor_message(
    payload: TutorMessageRequest,
    learner: Learner = Depends(get_current_learner),
    db: AsyncSession = Depends(get_db),
) -> TutorMessageResponse:
    requested_topic = await db.get(
        Topic, payload.topic_id, options=[selectinload(Topic.subject)]
    )
    if requested_topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")

    # FIX 15 Nov 2026 (grade-scoped visibility, ADR-026): /subjects and
    # /topics now hide any topic above the learner's own grade from the
    # picker, but a hidden-from-the-UI topic_id could still be POSTed
    # here directly -- this is the actual enforcement point, not just
    # the UI affordance. 403, not 404: the topic is real, the learner
    # just isn't allowed to be taught it yet.
    if requested_topic.subject.grade > learner.grade:
        raise HTTPException(
            status_code=403,
            detail="This topic is above your current grade.",
        )

    # NEW 13 Nov 2026 (ADR-016, student file attachments). Loaded before
    # the prerequisite/diagnosis work below so a bad attachment_ids entry
    # fails fast, before any other work on this turn.
    attachments = await _fetch_owned_attachments(db, learner.id, payload.attachment_ids)
    attachment_dicts = [_attachment_to_dict(a) for a in attachments]

    prerequisite_chain = await _resolve_prerequisite_chain(db, requested_topic)
    attempts_by_topic = await _fetch_scored_attempts_by_topic(
        db, learner.id, [t.id for t in prerequisite_chain]
    )

    # NEW 14 Nov 2026 (ADR-021, real RAG content grounding): diagnose_root_gap
    # is pure/cheap (no I/O over an already-fetched, small prerequisite
    # chain), so calling it here -- just to learn which topic will
    # actually be taught, in time to look up its grounding text -- and
    # then again inside prepare_tutor_turn() is a deliberate, documented
    # doubled call rather than threading a DB session through that
    # module's otherwise DB-free contract (see tutor_orchestration.py).
    diagnosis_preview = diagnose_root_gap(prerequisite_chain, attempts_by_topic)
    grounding_query_text = payload.message.strip() or requested_topic.name
    grounding_text = await get_grounding_text(
        db, diagnosis_preview.recommended_topic.id, grounding_query_text
    )

    prep = prepare_tutor_turn(
        learner, prerequisite_chain, attempts_by_topic, grounding_text=grounding_text
    )

    session = await _get_or_create_session(db, learner.id, prep.recommended_topic.id)

    history_stmt = (
        select(TutorMessage)
        .where(TutorMessage.session_id == session.id)
        .order_by(TutorMessage.created_at)
    )
    history_result = await db.execute(history_stmt)
    history = history_result.scalars().all()

    claude_messages = [{"role": m.role, "content": m.content} for m in history]

    # NEW 13 Nov 2026 (ADR-016): when the student attached files, Claude
    # gets the rich multimodal content (image vision blocks and/or
    # extracted PDF/docx text) for THIS turn only -- see
    # build_attachment_content_blocks. What gets PERSISTED below is a
    # plain-text summary instead (history_summary_for), so replaying this
    # turn in a later turn's history doesn't re-spend tokens resending an
    # image that was already answered.
    # FIX 13 Nov 2026 (ADR-016): payload.message can legitimately be ""
    # now (schema only requires message OR an attachment -- see
    # TutorMessageRequest's model_validator) -- an attachment-only turn
    # still needs SOME text block for Claude and for the persisted
    # history summary, so default to a plain instruction in that case.
    message_text = payload.message.strip() or (
        "Please look at the attached file and help me with it."
        if attachment_dicts
        else payload.message
    )

    if attachment_dicts:
        user_content = build_attachment_content_blocks(attachment_dicts)
        user_content.append({"type": "text", "text": message_text})
    else:
        user_content = message_text
    claude_messages.append({"role": "user", "content": user_content})

    persisted_content = history_summary_for(attachment_dicts, message_text)
    user_message = TutorMessage(session_id=session.id, role="user", content=persisted_content)
    db.add(user_message)
    await db.flush()  # need user_message.id to backfill the attachments below

    for attachment in attachments:
        attachment.session_id = session.id
        attachment.message_id = user_message.id

    reply_text = await _tutor_client.ask(prep.system_prompt, claude_messages)

    db.add(TutorMessage(session_id=session.id, role="assistant", content=reply_text))

    await db.commit()

    math_result = verify_tutor_response(reply_text)

    return TutorMessageResponse(
        session_id=session.id,
        topic_id=prep.recommended_topic.id,
        requested_topic_id=requested_topic.id,
        redirected=prep.diagnosis.redirected,
        reasoning_trace=prep.diagnosis.reasoning_trace,
        reply=reply_text,
        math_verified=math_result.verified,
        verification_warnings=math_result.warnings,
    )


@router.get("/ping")
async def ping() -> dict:
    """Cheap liveness check that doesn't touch the DB or the Anthropic API."""
    return {"status": "ok"}
