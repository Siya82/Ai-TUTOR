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
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
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
    # NEW 19 Nov 2026 (ADR-046; migration 0021): the part of the subject a
    # topic belongs to -- "Physics (Paper 1)" or "Chemistry (Paper 2)" for
    # Physical Sciences, None elsewhere. LEARN groups the topic list by it.
    section: Mapped[str | None] = mapped_column(String(40), nullable=True)

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
    # NEW 19 Nov 2026 (ADR-039, INSIGHTS; migration 0017). kind="office" is
    # a circuit/district office: its users are education officials, who log
    # in by picking their office like a teacher picks their school. A real
    # school sits in at most one circuit.
    kind: Mapped[str] = mapped_column(String(20), nullable=False, default="school", server_default="school")
    circuit_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("circuits.id"), nullable=True, index=True)
    # NEW 19 Nov 2026 (ADR-044, ADMIN; migration 0019): the school's profile,
    # kept by the school itself in ADMIN -> School settings.
    emis_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    province: Mapped[str | None] = mapped_column(String(40), nullable=True)
    quintile: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 1-5 (no-fee schools are 1-3)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    physical_address: Mapped[str | None] = mapped_column(String(300), nullable=True)
    # ...and its settings. These switch real behaviour (ADR-043 flows).
    parent_signup_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    viewer_invites_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    # NEW 20 Nov 2026 (deep scan M1, H5; migration 0022), both off by default:
    # require a recorded parent/guardian consent before a learner can use the
    # AI tutor; and a monthly AI spend cap for the school (US dollars).
    require_consent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    ai_budget_usd_month: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)

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

    # NEW 19 Nov 2026 (ADR-035, migration 0014). Learner-chosen; the tutor
    # may also explain in this language (see personalization.py). NULL or
    # "English" = no change.
    home_language: Mapped[str | None] = mapped_column(String(30), nullable=True)

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
    # NEW 20 Nov 2026 (deep scan M8): taken out of the bank after a report
    is_hidden: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
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

    # NEW 20 Nov 2026 (deep scan M5): set on a learner's question when it
    # matched a question in a test that was open for them -- the tutor then
    # coaches without solving, and the teacher can see it happened.
    test_assignment_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("assignments.id"), nullable=True)

    session: Mapped["TutorSession"] = relationship(back_populates="messages")


class VideoResource(Base):
    """
    A video linked to a topic.

    ADR-049 (20 Nov 2026): first used for THUTOra's own one-minute "What is
    this topic?" overviews (source "THUTOra", url /media/topic-videos/...),
    registered by scripts/topic_videos/register.py. ADR-005's catalogue of
    curated external video (Mindset Learn, Siyavula, Khan Academy) can use
    the same table with its own source.
    """

    __tablename__ = "video_resources"

    id: Mapped[uuid.UUID] = uuid_pk()
    topic_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("topics.id"), index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    source: Mapped[str] = mapped_column(String(100))  # e.g. "Mindset Learn", "Siyavula"
    duration_minutes: Mapped[int | None] = mapped_column(Integer)
    duration_seconds: Mapped[int | None] = mapped_column(Integer)  # ADR-049


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
    # NEW 19 Nov 2026 (code review 19 Nov #2; migration 0020): a teacher can
    # correct the AI's mark. When marked_by_user_id is set, is_correct is the
    # TEACHER's decision; teacher_note is shown to the learner with it.
    teacher_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    marked_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    marked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

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
    # NEW 19 Nov 2026 (code review 19 Nov #7; migration 0020): the teacher
    # closed it early -- no more answers, whatever the mode or due date.
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


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


class ConsentRecord(Base):
    """
    NEW 19 Nov 2026 (ADR-037, POPIA basics, migration 0015). A learner is a
    child under POPIA, so processing their personal information rests on a
    parent's/guardian's consent (or the school's own lawful basis). The
    school collects consent -- usually a signed form -- and a staff member
    records it here; THUTOra keeps who gave it, how, against which version
    of the privacy notice, and when it was withdrawn, if ever.
    """

    __tablename__ = "consent_records"

    id: Mapped[uuid.UUID] = uuid_pk()
    learner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("learners.id"), nullable=False, index=True)
    given_by_name: Mapped[str] = mapped_column(String(100), nullable=False)
    relationship_to_learner: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g. "Mother", "Guardian"
    method: Mapped[str] = mapped_column(String(30), nullable=False)  # "signed_form" | "parent_portal" | "other"
    notice_version: Mapped[str] = mapped_column(String(20), nullable=False)
    recorded_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


# ---------------------------------------------------------------------------
# NEW 19 Nov 2026 (ADR-038, CONNECT -- parents; migration 0016).
# A parent/guardian is a User with role="parent" in the child's school,
# logging in with a school-issued number like staff do. They are linked to
# one or more learners; they see those children's progress (never their
# tutor conversations) and the school's notices, which they can acknowledge.
# ---------------------------------------------------------------------------


class ParentLink(Base):
    __tablename__ = "parent_links"
    __table_args__ = (UniqueConstraint("parent_user_id", "learner_id", name="uq_parent_link"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    parent_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    learner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("learners.id"), nullable=False, index=True)
    relationship_to_learner: Mapped[str] = mapped_column(String(50), nullable=False, default="Parent")
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)
    # NEW 19 Nov 2026 (ADR-043, migration 0018). "guardian" = a parent or
    # guardian (verified by the school or by matching the school's record);
    # "viewer" = someone a guardian invited (e.g. a grandparent): sees
    # progress, not notices, and can be removed by the guardian or school.
    kind: Mapped[str] = mapped_column(String(20), nullable=False, default="guardian", server_default="guardian")
    invited_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class LearnerGuardian(Base):
    """
    NEW 19 Nov 2026 (ADR-043). The parent/guardian contact details the
    SCHOOL holds for a learner (captured at enrolment, or later from
    SA-SAMS). They are the trust anchor for parent self-sign-up: a parent
    can only connect to a learner if the cellphone number they verify by
    SMS matches one recorded here. parent_user_id is set once they sign up.
    """

    __tablename__ = "learner_guardians"

    id: Mapped[uuid.UUID] = uuid_pk()
    learner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("learners.id"), nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    relationship_to_learner: Mapped[str] = mapped_column(String(50), nullable=False, default="Parent")
    cellphone: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)  # +27XXXXXXXXX
    email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    parent_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)


class SignupCode(Base):
    """NEW 19 Nov 2026 (ADR-043). A one-time SMS code for parent self-sign-up (hashed, 10 minutes, 5 tries)."""

    __tablename__ = "signup_codes"

    id: Mapped[uuid.UUID] = uuid_pk()
    school_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("schools.id"), nullable=False, index=True)
    cellphone: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)


class ViewerInvite(Base):
    """NEW 19 Nov 2026 (ADR-043). A guardian's one-time invite for a viewer (e.g. a grandparent), 7 days."""

    __tablename__ = "viewer_invites"

    id: Mapped[uuid.UUID] = uuid_pk()
    school_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("schools.id"), nullable=False, index=True)
    learner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("learners.id"), nullable=False, index=True)
    invited_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    viewer_name: Mapped[str] = mapped_column(String(100), nullable=False)
    relationship_to_learner: Mapped[str] = mapped_column(String(50), nullable=False)
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)


class SchoolNotice(Base):
    __tablename__ = "school_notices"

    id: Mapped[uuid.UUID] = uuid_pk()
    school_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("schools.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    grade: Mapped[int | None] = mapped_column(Integer, nullable=True)  # None = whole school
    requires_ack: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)


class NoticeAck(Base):
    __tablename__ = "notice_acks"
    __table_args__ = (UniqueConstraint("notice_id", "user_id", name="uq_notice_ack"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    notice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("school_notices.id"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    acked_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)


# ---------------------------------------------------------------------------
# NEW 19 Nov 2026 (ADR-039, INSIGHTS; migration 0017). The department's
# structure above schools: district -> circuit -> school. An official (User
# role "official", belonging to an office School) is assigned to a district
# or a circuit and sees aggregated outcomes for every school under it --
# never individual learners' names or work.
# ---------------------------------------------------------------------------


class District(Base):
    __tablename__ = "districts"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    province: Mapped[str] = mapped_column(String(60), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)


class Circuit(Base):
    __tablename__ = "circuits"

    id: Mapped[uuid.UUID] = uuid_pk()
    district_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("districts.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)


class OfficialAssignment(Base):
    """Exactly one of district_id / circuit_id is set."""

    __tablename__ = "official_assignments"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    district_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("districts.id"), nullable=True, index=True)
    circuit_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("circuits.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)


class SchoolRegistration(Base):
    """
    NEW 19 Nov 2026 (ADR-044). A school asking to join THUTOra, from the
    public "Register your school" form. Zynora reviews it, and approving it
    (scripts/manage_registrations.py) creates the school and its principal --
    the same onboarding step as scripts/provision_school.py.
    """

    __tablename__ = "school_registrations"

    id: Mapped[uuid.UUID] = uuid_pk()
    school_name: Mapped[str] = mapped_column(String(200), nullable=False)
    emis_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    province: Mapped[str] = mapped_column(String(40), nullable=False)
    contact_name: Mapped[str] = mapped_column(String(100), nullable=False)
    contact_role: Mapped[str] = mapped_column(String(50), nullable=False)
    contact_cellphone: Mapped[str] = mapped_column(String(20), nullable=False)
    contact_email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    learner_estimate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", server_default="pending")
    school_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("schools.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class AuditEvent(Base):
    """
    NEW 19 Nov 2026 (code review 19 Nov #11; migration 0020). Who did what
    sensitive thing, when: password resets, account switch-off, role grants,
    consent, data export/deletion, mark overrides, school settings. Kept for
    POPIA accountability; never holds passwords or tutor conversations.
    """

    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = uuid_pk()
    school_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("schools.id"), nullable=True, index=True)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    target_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive, index=True)


class RateEvent(Base):
    """
    NEW 20 Nov 2026 (deep scan L6). One row per rate-limited event (a failed
    login, an SMS code, an invite attempt...). Counting rows in the database
    -- not a dict in one server's memory -- keeps limits correct when THUTOra
    runs on several servers. Old rows are removed by scripts/retention.py.
    """

    __tablename__ = "rate_events"
    __table_args__ = (Index("ix_rate_events_key_created", "key", "created_at"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    key: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive, nullable=False)


class AiUsage(Base):
    """
    NEW 20 Nov 2026 (deep scan H5). One row per AI call: who for, what for,
    which model and how many tokens -- never the text. Cost is worked out
    from these with the current price list (app/services/ai_cost.py), so the
    platform knows what each school costs to run.
    """

    __tablename__ = "ai_usage"

    id: Mapped[uuid.UUID] = uuid_pk()
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive, index=True)
    school_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("schools.id"), nullable=True, index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    feature: Mapped[str] = mapped_column(String(30), nullable=False)  # tutor | marking | translation
    model: Mapped[str] = mapped_column(String(80), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cache_read_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cache_write_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class QuestionReport(Base):
    """
    NEW 20 Nov 2026 (deep scan M8). A teacher flags a bank question as wrong
    or unclear. Management (and Zynora) review it; a hidden question is no
    longer offered for new assignments or practice.
    """

    __tablename__ = "question_reports"

    id: Mapped[uuid.UUID] = uuid_pk()
    question_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("questions.id"), nullable=False, index=True)
    reported_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    school_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("schools.id"), nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open", server_default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
