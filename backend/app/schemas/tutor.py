"""
Pydantic request/response schemas for POST /tutor/message.

REBUILD NOTE: rebuilt from REBUILD_SPEC.md Section 1 -- not recovered
code. math_verified / verification_warnings were added once MathGuard
(app/services/math_guard.py) existed to actually populate them -- see
REBUILD_SPEC.md Section 1, step 5 of the rebuild priority order.
"""

from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.schemas.books import BookContext  # ADR-032


class TutorMessageRequest(BaseModel):
    # FIX 14 Nov 2026 (ADR-017, student login): learner_id used to be
    # taken straight from the request body -- the whole "no auth yet"
    # gap REBUILD_SPEC.md Section 2 step 8 flagged. It's gone now; the
    # learner is resolved server-side from the Authorization bearer
    # token via app/core/security.py's get_current_learner, in
    # app/routers/tutor.py.
    topic_id: UUID
    session_id: UUID | None = None
    # FIX 13 Nov 2026 (ADR-016): used to be Field(min_length=1), which
    # rejected a perfectly normal "just attach a photo, no caption"
    # turn with a 422 -- the frontend doesn't force any text when an
    # attachment is ready to send (see ChatScreen.jsx's handleSend).
    # The model_validator below still requires SOME content: either a
    # non-blank message or at least one attachment.
    message: str = Field(default="", max_length=4000)  # code review #9
    # NEW 13 Nov 2026 (ADR-016): files the student attached via a prior
    # POST /attachments call, in the order they should be presented to
    # Claude. Optional and defaults to empty so every existing caller
    # (and every existing test) keeps working unchanged.
    attachment_ids: list[UUID] = Field(default_factory=list, max_length=10)
    # NEW 17 Nov 2026 (ADR-032): set when the learner asks from the e-book
    # reader. The server loads the page text itself.
    book_context: BookContext | None = None

    @model_validator(mode="after")
    def _require_message_or_attachment(self) -> "TutorMessageRequest":
        if not self.message.strip() and not self.attachment_ids and self.book_context is None:
            raise ValueError(
                "message must not be blank unless at least one attachment_id is provided"
            )
        return self


class TutorMessageResponse(BaseModel):
    session_id: UUID
    topic_id: UUID             # the topic actually taught -- may differ from requested_topic_id
    requested_topic_id: UUID
    redirected: bool
    reasoning_trace: list[str]
    reply: str
    math_verified: bool
    verification_warnings: list[str]
