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

from app.core.clock import utcnow_naive

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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)


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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)

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
    # NEW 17 Nov 2026 (code review #6, migration 0013). Carried in every
    # token as "ver"; bumped on password change/reset and deactivation so
    # tokens issued before that stop working immediately.
    token_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)
    # NEW 17 Nov 2026 (ADR-031). Staff need a name to be listed/allocated;
    # students keep theirs on Learner.display_name, so this stays NULL for them.
    display_name: Mapped[str | None] = mapped_column(String(100), nullable=True)

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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)

    # Learner-chosen, changeable anytime — NOT a diagnosed "learning style".
    # See docs/ADR-002-personalization.md for why this is a preference,
    # not a fixed label. Values: "visual" | "practical" | "auditory" | "balanced"
    preferred_modality: Mapped[str] = mapped_column(String(20), default="balanced")

    # NEW 15 Nov 2026 (ADR-027, dev/admin diagnosis bypass). Default False
    # for every real student -- diagnose_root_gap()'s redirect-on-gap
    # behaviour (ADR-007) is untouched for them. True ONLY for Siya's own
    # dev/admin account (seed_dev_data.py's get_or_create_dev_learner),
    # which has zero attempt history on everything and would otherwise
    # ALWAYS get redirected to the deepest foundational prerequisite no
    # matter which grade it asks about -- see app/services/tutor_orchestration.py's
    # prepare_tutor_turn() for where this is actually read.
    skip_diagnosis: Mapped[bool] = mapped_column(Boolean, default=False)

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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)

    # NEW 15 Nov 2026 (ADR-028, assignments). None for every seeded/
    # diagnostic/AI-generated question exactly as before -- set to the
    # authoring teacher's User.id for a custom question a teacher wrote
    # themselves. No separate boolean needed: "is this teacher-authored"
    # is just created_by_user_id IS NOT NULL. is_diagnostic/is_ai_generated
    # both stay False for a teacher-authored question, since it is
    # neither of those existing categories.
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )


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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)

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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)

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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)


class Attempt(Base):
    """A single learner response to a question, with AI-marked outcome."""

    __tablename__ = "attempts"

    id: Mapped[uuid.UUID] = uuid_pk()
    learner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("learners.id"))
    question_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("questions.id"))
    learner_response: Mapped[str] = mapped_column(Text, nullable=False)
    is_correct: Mapped[bool | None] = mapped_column(Boolean)  # null until marked
    ai_feedback: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)

    # NEW 15 Nov 2026 (ADR-028, assignments). None for every ordinary
    # diagnostic/adaptive-practice attempt exactly as before -- set only
    # when this response was submitted against a specific question of a
    # specific assignment, via app/services/assignments.py's
    # submit_assignment_answer(). Every existing reader of Attempt
    # (diagnosis.py, personalization.py, dashboard.py, risk_assessment.py)
    # is unaffected, since none of them filter on this column -- Attempt
    # stays the one source of truth for mastery, assignment-origin or not.
    assignment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("assignments.id"), nullable=True
    )

    learner: Mapped["Learner"] = relationship(back_populates="attempts")


class Assignment(Base):
    """
    One piece of work a teacher issues: a title, optional instructions
    and due date, a set of questions (assignment_questions, seeded
    and/or the teacher's own custom ones), and the students it was
    actually issued to (assignment_targets). See docs/ADR-028-assignments.md.
    """

    __tablename__ = "assignments"

    id: Mapped[uuid.UUID] = uuid_pk()
    school_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("schools.id"))
    teacher_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    instructions: Mapped[str | None] = mapped_column(Text)
    due_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)

    # NEW 15 Nov 2026 (ADR-029). "practice" (default, matches every
    # assignment created before this) shows AI feedback the instant a
    # student answers, same as today. "test" withholds is_correct/
    # ai_feedback (app/routers/learner_assignments.py) until the
    # teacher flips results_released via release_assignment_results().
    # The real mark is always computed and stored on Attempt the
    # moment the student answers -- only what's shown to the student
    # is gated, never what's recorded.
    mode: Mapped[str] = mapped_column(String(20), default="practice")
    results_released: Mapped[bool] = mapped_column(Boolean, default=False)


class AssignmentQuestion(Base):
    """
    The ordered many-to-many between an Assignment and the Question rows
    it contains. A Question (seeded or teacher-authored) can belong to
    more than one Assignment -- it is not exclusive to the one it was
    first added to.
    """

    __tablename__ = "assignment_questions"
    __table_args__ = (UniqueConstraint("assignment_id", "question_id", name="uq_assignment_question"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    assignment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("assignments.id"))
    question_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("questions.id"))
    order_index: Mapped[int] = mapped_column(Integer, default=0)

    # NEW 15 Nov 2026 (ADR-029). The point value this question is
    # worth within THIS assignment -- the same Question can be worth a
    # different number of marks in a different assignment, since marks
    # describe how the question is being used here, not a property of
    # the question itself. Defaults to 1, matching every assignment
    # question created before this (a correct answer always counted
    # for exactly one point).
    marks: Mapped[int] = mapped_column(Integer, default=1)


class AssignmentTarget(Base):
    """
    Which Learners an Assignment was actually issued to. No Class/group
    concept yet -- a teacher targets students individually, picked from
    the same roster the ADR-024 admin UI already lists.
    """

    __tablename__ = "assignment_targets"
    __table_args__ = (UniqueConstraint("assignment_id", "learner_id", name="uq_assignment_target"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    assignment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("assignments.id"))
    learner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("learners.id"))


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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)


# ---------------------------------------------------------------------------
# NEW 17 Nov 2026 (ADR-031, school roles and scoping). What a staff account
# may see/do is no longer "everything in my school": it is resolved from
# these tables by app/services/school_scope.py on every request.
# ---------------------------------------------------------------------------


class SchoolClass(Base):
    """A class/group of learners in one grade, e.g. "10A". Named SchoolClass
    because `class` is a Python keyword."""

    __tablename__ = "school_classes"
    __table_args__ = (UniqueConstraint("school_id", "name", name="uq_school_class_name"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    school_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("schools.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    grade: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)


class ClassMember(Base):
    """A learner's membership of a class. A learner may be in several classes."""

    __tablename__ = "class_members"
    __table_args__ = (UniqueConstraint("class_id", "learner_id", name="uq_class_member"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    class_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("school_classes.id"), nullable=False)
    learner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("learners.id"), nullable=False)


class TeachingAllocation(Base):
    """A teacher teaches one subject (Subject rows carry the grade) to one
    class. The allocation is what scopes a plain teacher's access."""

    __tablename__ = "teaching_allocations"
    __table_args__ = (
        UniqueConstraint("teacher_user_id", "subject_id", "class_id", name="uq_teaching_allocation"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    school_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("schools.id"), nullable=False)
    teacher_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    subject_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("subjects.id"), nullable=False)
    # NULL (migration 0012) = the WHOLE grade: every learner in the school in
    # the subject's grade, without needing classes to be set up first.
    class_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("school_classes.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)


class StaffRole(Base):
    """A school-level role grant: principal, deputy_principal,
    departmental_head or school_admin. A departmental head's department is
    expressed as one row per subject name (optionally limited to one grade)."""

    __tablename__ = "staff_roles"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    school_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("schools.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(30), nullable=False)
    subject_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    grade: Mapped[int | None] = mapped_column(Integer, nullable=True)
    granted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)


# ---------------------------------------------------------------------------
# NEW 17 Nov 2026 (ADR-032, e-book library and reader).
# ---------------------------------------------------------------------------


class Book(Base):
    """An openly-licensed textbook (e.g. Siyavula CC-BY) a learner can read
    and ask THUTOra about. The PDF itself lives in
    backend/content_sources/books/<file_name> and is not committed."""

    __tablename__ = "books"

    id: Mapped[uuid.UUID] = uuid_pk()
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    subject_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("subjects.id"), nullable=False)
    publisher: Mapped[str | None] = mapped_column(String(100))
    licence: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g. "CC-BY 3.0"
    attribution: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(500))
    file_name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    page_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # NEW (ADR-032 ePub addendum, migration 0010): "pdf" -> BookPage is a
    # printed page; "epub" -> BookPage is a section split at headings.
    format: Mapped[str] = mapped_column(String(10), nullable=False, default="pdf")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)


class BookPage(Base):
    """Extracted text of one page: the low-data text view, the source of
    selectable text, and the passage sent to the tutor."""

    __tablename__ = "book_pages"
    __table_args__ = (UniqueConstraint("book_id", "page_number", name="uq_book_page"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    book_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("books.id"), nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-based: PDF page, or ePub section number
    text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # ePub only (migration 0010): the section's sanitised HTML and heading
    title: Mapped[str | None] = mapped_column(String(300), nullable=True)
    html: Mapped[str | None] = mapped_column(Text, nullable=True)
    chapter: Mapped[str | None] = mapped_column(String(300), nullable=True)  # migration 0011


class BookTopicRange(Base):
    """Optional: pages start_page..end_page (inclusive) cover this CAPS topic."""

    __tablename__ = "book_topic_ranges"

    id: Mapped[uuid.UUID] = uuid_pk()
    book_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("books.id"), nullable=False)
    topic_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("topics.id"), nullable=False)
    start_page: Mapped[int] = mapped_column(Integer, nullable=False)
    end_page: Mapped[int] = mapped_column(Integer, nullable=False)
