"""
Pydantic request/response schemas for POST /tutor/message.

REBUILD NOTE: rebuilt from REBUILD_SPEC.md Section 1 -- not recovered
code. math_verified / verification_warnings were added once MathGuard
(app/services/math_guard.py) existed to actually populate them -- see
REBUILD_SPEC.md Section 1, step 5 of the rebuild priority order.
"""

from uuid import UUID

from pydantic import BaseModel, Field


class TutorMessageRequest(BaseModel):
    learner_id: UUID
    topic_id: UUID
    message: str = Field(min_length=1)
    # NEW 13 Nov 2026 (ADR-016): files the student attached via a prior
    # POST /attachments call, in the order they should be presented to
    # Claude. Optional and defaults to empty so every existing caller
    # (and every existing test) keeps working unchanged.
    attachment_ids: list[UUID] = Field(default_factory=list)


class TutorMessageResponse(BaseModel):
    session_id: UUID
    topic_id: UUID             # the topic actually taught -- may differ from requested_topic_id
    requested_topic_id: UUID
    redirected: bool
    reasoning_trace: list[str]
    reply: str
    math_verified: bool
    verification_warnings: list[str]
