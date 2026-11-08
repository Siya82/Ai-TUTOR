"""
Core database models for the AI CAPS Tutor pilot.

Schema design notes (see docs/BUILD_LOG.md for rationale):
- `Subject` and `Topic` model the CAPS curriculum structure directly, so the
  same tables serve both Pure Mathematics and Physical Science without
  subject-specific tables.
- `ContentChunk` holds embedded CAPS source material (syllabus text, past
  paper questions/memos) for RAG grounding via pgvector.
- `Attempt` is the single table that both the diagnostic assessment and the
  ongoing adaptive practice loop write to — mastery is computed from this,
  not stored as a separate mutable field, so it's always re-derivable.

RECOVERY NOTE: this file is reconstructed verbatim from a read performed on
2026-08-26. Per later project memory, authentication fields/tables (bcrypt
password hash, JWT-related columns) and CAPS `term` / `week_allocation`
fields on `Topic` were added after this snapshot and are NOT reflected
below — see REBUILD_SPEC.md for what's known about those additions.
"""

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )


class Subject(Base):
    """A CAPS subject, e.g. 'Pure Mathematics' or 'Physical Science'."""

    __tablename__ = "subjects"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    grade: Mapped[int] = mapped_column(Integer, nullable=False)  # e.g. 10

    topics: Mapped[list["Topic"]] = relationship(back_populates="subject")

    __table_args__ = (UniqueConstraint("name", "grade", name="uq_subject_grade"),)


class Topic(Base):
    """
    A CAPS topic/concept within a subject, e.g. 'Functions' or
    'Newton's Laws'. Self-referential `prerequisite_id` lets us express
    simple prerequisite chains without a full knowledge graph (that's a
    v2 concern per the roadmap).
    """

    __tablename__ = "topics"

    id: Mapped[uuid.UUID] = uuid_pk()
    subject_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("subjects.id"))
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    caps_reference: Mapped[str | None] = mapped_column(String(50))  # e.g. syllabus clause
    prerequisite_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("topics.id"))

    subject: Mapped["Subject"] = relationship(back_populates="topics")


class ContentChunk(Base):
    """
    A chunk of grounding content (syllabus text, past paper Q&A, memo
    explanation) with its embedding, used for RAG when the tutor answers
    or generates practice questions. Populated by the ingestion pipeline
    (scripts/ — not yet built, see BUILD_LOG.md).
    """

    __tablename__ = "content_chunks"

    id: Mapped[uuid.UUID] = uuid_pk()
    topic_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("topics.id"))
    source: Mapped[str] = mapped_column(String(200))  # e.g. "2023 Paper 1 Memo"
    text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(1536))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Learner(Base):
    __tablename__ = "learners"

    id: Mapped[uuid.UUID] = uuid_pk()
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    grade: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Learner-chosen, changeable anytime — NOT a diagnosed "learning style".
    # See docs/ADR-002-personalization.md for why this is a preference,
    # not a fixed label. Values: "visual" | "practical" | "auditory" | "balanced"
    preferred_modality: Mapped[str] = mapped_column(String(20), default="balanced")

    attempts: Mapped[list["Attempt"]] = relationship(back_populates="learner")

    # Note: pace/difficulty tier ("slower"/"gifted" in everyday terms) is
    # deliberately NOT a stored column. It's computed on the fly from
    # `attempts` by app.services.personalization.compute_pace_tier(), so it
    # can never go stale and can differ per topic. See ADR-002.

    # RECOVERY NOTE: per later project memory, real auth was added after
    # this snapshot — expect additional columns here on rebuild, e.g. a
    # hashed_password (bcrypt via passlib) and whatever fields the JWT
    # (python-jose) flow needs (likely an email/username unique column).


class Question(Base):
    """
    A question, either curated (diagnostic question bank) or AI-generated
    (adaptive practice). `is_diagnostic` distinguishes the two so the fixed
    diagnostic bank (Step 3 of the roadmap) is never accidentally mixed with
    generated practice questions (Step 5).
    """

    __tablename__ = "questions"

    id: Mapped[uuid.UUID] = uuid_pk()
    topic_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("topics.id"))
    text: Mapped[str] = mapped_column(Text, nullable=False)
    model_answer: Mapped[str] = mapped_column(Text, nullable=False)
    is_diagnostic: Mapped[bool] = mapped_column(Boolean, default=False)
    is_ai_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class TutorSession(Base):
    """
    One tutoring conversation, scoped to a learner + topic. Kept separate
    per topic (rather than one long-running session per learner) so
    context stays focused and the personalization pace tier — which is
    computed per topic — stays meaningful for the conversation it's shaping.
    """

    __tablename__ = "tutor_sessions"

    id: Mapped[uuid.UUID] = uuid_pk()
    learner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("learners.id"))
    topic_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("topics.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    messages: Mapped[list["TutorMessage"]] = relationship(
        back_populates="session", order_by="TutorMessage.created_at"
    )


class TutorMessage(Base):
    """
    A single turn in a tutor session. Persisting full history (not just
    the latest exchange) is what lets a learner's "why?" follow-up be
    answered with awareness of exactly what was already explained,
    per ADR-003.
    """

    __tablename__ = "tutor_messages"

    id: Mapped[uuid.UUID] = uuid_pk()
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tutor_sessions.id"))
    role: Mapped[str] = mapped_column(String(20))  # "user" | "assistant"
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    session: Mapped["TutorSession"] = relationship(back_populates="messages")


class VideoResource(Base):
    """
    Curated external video, linked to a topic — not hosted or generated
    by this platform. See ADR-005: free CAPS-aligned video already exists
    (Mindset Learn, Siyavula, Khan Academy); this table catalogues it.
    """

    __tablename__ = "video_resources"

    id: Mapped[uuid.UUID] = uuid_pk()
    topic_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("topics.id"))
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    source: Mapped[str] = mapped_column(String(100))  # e.g. "Mindset Learn", "Siyavula"
    duration_minutes: Mapped[int | None] = mapped_column(Integer)


class Practical(Base):
    """
    A CAPS-prescribed practical experiment, e.g. "Reaction of magnesium
    with hydrochloric acid". Deliberately scoped to the official practical
    list, not an open sandbox — see ADR-005. `calculation_key` maps to a
    registered function in app/services/labs.py that computes real results
    from learner-provided inputs; the LLM never computes lab results itself.
    """

    __tablename__ = "practicals"

    id: Mapped[uuid.UUID] = uuid_pk()
    topic_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("topics.id"))
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    caps_reference: Mapped[str | None] = mapped_column(String(50))
    instructions: Mapped[str] = mapped_column(Text, nullable=False)
    calculation_key: Mapped[str] = mapped_column(String(100), nullable=False)
    phet_simulation_url: Mapped[str | None] = mapped_column(String(500))  # Tier 1, if applicable


class PracticalRun(Base):
    """One learner's attempt at a practical: their inputs and the computed (real) outputs."""

    __tablename__ = "practical_runs"

    id: Mapped[uuid.UUID] = uuid_pk()
    learner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("learners.id"))
    practical_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("practicals.id"))
    inputs_json: Mapped[str] = mapped_column(Text, nullable=False)  # JSON-encoded input params
    outputs_json: Mapped[str] = mapped_column(Text, nullable=False)  # JSON-encoded computed results
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Attempt(Base):
    """A single learner response to a question, with AI-marked outcome."""

    __tablename__ = "attempts"

    id: Mapped[uuid.UUID] = uuid_pk()
    learner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("learners.id"))
    question_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("questions.id"))
    learner_response: Mapped[str] = mapped_column(Text, nullable=False)
    is_correct: Mapped[bool | None] = mapped_column(Boolean)  # null until marked
    ai_feedback: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    learner: Mapped["Learner"] = relationship(back_populates="attempts")
