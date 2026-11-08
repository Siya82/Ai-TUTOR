"""
POST /tutor/message -- the real tutor conversation endpoint.

REBUILD NOTE: rebuilt from REBUILD_SPEC.md Section 1 -- not recovered
code. Wires diagnosis.py / personalization.py / tutor_orchestration.py /
tutor.py / math_guard.py (all rebuilt from spec, see each file's own
REBUILD NOTE) into a real endpoint against the recovered 11-table
schema.

Deliberately NOT included yet (later steps, not this one):
- Authentication -- REBUILD_SPEC.md Section 2, step 8. These endpoints
  are unauthenticated for now, same as the recovered dashboard router.
- RAG grounding -- content_chunks ingestion is still a placeholder.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models import Attempt, Learner, Question, Topic, TutorMessage, TutorSession
from app.schemas.tutor import TutorMessageRequest, TutorMessageResponse
from app.services.math_guard import verify_tutor_response
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
    """Walks Topic.prerequisite_id repeatedly, deepest topic last."""
    chain = [topic]
    seen = {topic.id}
    current = topic
    for _ in range(_MAX_PREREQUISITE_DEPTH):
        if current.prerequisite_id is None or current.prerequisite_id in seen:
            break
        prereq = await db.get(Topic, current.prerequisite_id)
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


@router.post("/message", response_model=TutorMessageResponse)
async def send_tutor_message(
    payload: TutorMessageRequest,
    db: AsyncSession = Depends(get_db),
) -> TutorMessageResponse:
    learner = await db.get(Learner, payload.learner_id)
    if learner is None:
        raise HTTPException(status_code=404, detail="Learner not found")

    requested_topic = await db.get(Topic, payload.topic_id)
    if requested_topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")

    prerequisite_chain = await _resolve_prerequisite_chain(db, requested_topic)
    attempts_by_topic = await _fetch_scored_attempts_by_topic(
        db, learner.id, [t.id for t in prerequisite_chain]
    )

    prep = prepare_tutor_turn(learner, prerequisite_chain, attempts_by_topic)

    session = await _get_or_create_session(db, learner.id, prep.recommended_topic.id)

    history_stmt = (
        select(TutorMessage)
        .where(TutorMessage.session_id == session.id)
        .order_by(TutorMessage.created_at)
    )
    history_result = await db.execute(history_stmt)
    history = history_result.scalars().all()

    claude_messages = [{"role": m.role, "content": m.content} for m in history]
    claude_messages.append({"role": "user", "content": payload.message})

    db.add(TutorMessage(session_id=session.id, role="user", content=payload.message))

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
