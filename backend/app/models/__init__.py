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

NEW 14 Nov 2026 (ADR-017, student login): `School` and `User` below are
a fresh, greenfield addition for this rebuild (not a recovery of
whatever the original app did for auth, if anything) -- a real
identity/credential layer kept deliberately separate from `Learner`
(the pedagogical profile), linked by `Learner.user_id`. See the ADR for
why this shape was chosen over bolting auth fields onto `Learner`
directly.
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
    # NEW 15 Nov 2026 (live-test finding): topics were being listed
    # alphabetically by name (see app/routers/topics.py), not in the
    # term-by-term CAPS teaching order every seed_dev_data.py topic list
    # is actually already written in -- a student picking a subject in
    # the sidebar saw e.g. "Algebraic Expressions" after "Analytical
    # Geometry" purely because A-l comes before A-n. order_index is each
    # topic's zero-based position within its subject's own topic list in
    # seed_dev_data.py (which follows the real DBE ATP term order, per
    # every subject-addition ADR), set/refreshed there on every seed run.
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

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


class School(Base):
    """
    NEW 14 Nov 2026 (ADR-017, student login). Deliberately minimal --
    just enough to scope students to the institution that enrolled
    them. `name` is not unique: two schools can share a name in
    practice (common South African school names repeat across
    provinces), so students are scoped by `school_id`, never by name
    matching.
    """

    __tablename__ = "schools"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    users: Mapped[list["User"]] = relationship(back_populates="school")


class User(Base):
    """
    NEW 14 Nov 2026 (ADR-017, student login). The auth/identity row --
    deliberately separate from `Learner` (the pedagogical profile) so
    teacher/parent/admin roles can be added later without reworking
    this table or migrating `Learner` itself. `role` is a plain string,
    not a DB enum, for the same reason: adding a new role later is a
    data change, not a migration.

    `student_number` only has to be unique WITHIN its own school (see
    the UniqueConstraint below), matching how real school-issued
    numbers work -- two different schools will reuse the same numbers.
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = uuid_pk()
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="student")
    school_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("schools.id"), nullable=False)
    student_number: Mapped[str] = mapped_column(String(50), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Set True whenever a temporary password was issued at provisioning
    # time (app/services/auth.py's provision_student) -- cleared the
    # moment the student successfully calls POST /auth/change-password.
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    school: Mapped["School"] = relationship(back_populates="users")
    learner: Mapped["Learner"] = relationship(back_populates="user", uselist=False)

    __table_args__ = (
        UniqueConstraint("school_id", "student_number", name="uq_user_school_student_number"),
    )


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

    # NEW 14 Nov 2026 (ADR-017, student login). Nullable so existing dev
    # data doesn't need a forced migration path immediately -- but every
    # real student going forward gets both rows created together by
    # app/services/auth.py's provision_student(). This is the seam
    # between the pedagogical profile (this table) and the auth/identity
    # row (User): one Learner is owned by at most one User.
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"), unique=True, nullable=True
    )
    user: Mapped["User | None"] = relationship(back_populates="learner")

    # Note: pace/difficulty tier ("slower"/"gifted" in everyday terms) is
    # deliberately NOT a stored column. It's computed on the fly from
    # `attempts` by app.services.personalization.compute_pace_tier(), so it
    # can never go stale and can differ per topic. See ADR-002.


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


class Attachment(Base):
    """
    A file a student attached to (or alongside) a tutor message -- an
    image (sent to Claude as a vision block), a PDF, or a Word document
    (both text-extracted server-side). See
    docs/ADR-016-student-file-attachments.md.

    `session_id`/`message_id` start NULL: the upload endpoint
    (POST /attachments) runs before the student's message is sent, so
    the attachment exists before any session/message row does. Both get
    backfilled by POST /tutor/message once it creates the resulting
    TutorMessage, so a persisted attachment is always traceable back to
    the learner AND, once sent, the exact session/message it was part of.
    """

    __tablename__ = "attachments"

    id: Mapped[uuid.UUID] = uuid_pk()
    learner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("learners.id"))
    session_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tutor_sessions.id"))
    message_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tutor_messages.id"))
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)  # "image" | "pdf" | "docx"
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    extracted_text: Mapped[str | None] = mapped_column(Text)  # PDF/docx only; null for images
    extraction_warning: Mapped[str | None] = mapped_column(Text)  # e.g. a scanned PDF with no text layer
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
