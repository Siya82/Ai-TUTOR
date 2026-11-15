"""add assignments (teacher-authored questions, issued and tracked) -- ADR-028

See docs/ADR-028-assignments.md. Adds Question.created_by_user_id
(nullable -- None for every seeded/diagnostic/AI-generated question
exactly as today, set only for a teacher-authored custom question) and
Attempt.assignment_id (nullable -- set only when a response was
submitted in the context of a specific assignment question; every
existing read path in diagnosis.py/personalization.py/dashboard.py/
risk_assessment.py is unaffected, since none of them filter on it).

Three new tables: assignments (one per issued piece of work, scoped to
a school and the teacher who created it), assignment_questions (the
ordered many-to-many between an assignment and the Question rows it
contains -- a question, seeded or custom, can belong to more than one
assignment), and assignment_targets (which Learners this assignment
was actually issued to -- no Class/group concept yet, a teacher targets
students individually from the same roster ADR-024's admin UI lists).

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "questions",
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
    )

    op.create_table(
        "assignments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "school_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("schools.id"), nullable=False
        ),
        sa.Column(
            "teacher_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("instructions", sa.Text, nullable=True),
        sa.Column("due_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=True),
    )

    op.add_column(
        "attempts",
        sa.Column(
            "assignment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("assignments.id"),
            nullable=True,
        ),
    )

    op.create_table(
        "assignment_questions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "assignment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("assignments.id"),
            nullable=False,
        ),
        sa.Column(
            "question_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("questions.id"), nullable=False
        ),
        sa.Column("order_index", sa.Integer, nullable=False, server_default="0"),
        sa.UniqueConstraint("assignment_id", "question_id", name="uq_assignment_question"),
    )

    op.create_table(
        "assignment_targets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "assignment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("assignments.id"),
            nullable=False,
        ),
        sa.Column(
            "learner_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("learners.id"), nullable=False
        ),
        sa.UniqueConstraint("assignment_id", "learner_id", name="uq_assignment_target"),
    )


def downgrade() -> None:
    op.drop_table("assignment_targets")
    op.drop_table("assignment_questions")
    op.drop_column("attempts", "assignment_id")
    op.drop_table("assignments")
    op.drop_column("questions", "created_by_user_id")
