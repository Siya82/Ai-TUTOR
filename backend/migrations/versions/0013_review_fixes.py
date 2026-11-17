"""Code review fixes (17 Nov 2026): token_version, foreign-key indexes,
one whole-grade allocation per teacher+subject.

- users.token_version: bumped on password change/reset and deactivation,
  so older tokens stop working straight away (review #6).
- An index on every foreign-key column (review #11). Postgres doesn't
  create these automatically; lookups like "this learner's attempts"
  were full scans.
- A partial unique index for whole-grade allocations (review #19): the
  existing unique constraint can't see duplicates when class_id is NULL.

Revision ID: 0013
Revises: 0012
Create Date: 2026-11-17
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (table, column) for every foreign key in app/models at 0012.
FK_COLUMNS = [
    ("topics", "subject_id"),
    ("topics", "prerequisite_id"),
    ("content_chunks", "topic_id"),
    ("users", "school_id"),
    ("learners", "user_id"),
    ("questions", "topic_id"),
    ("questions", "created_by_user_id"),
    ("tutor_sessions", "learner_id"),
    ("tutor_sessions", "topic_id"),
    ("tutor_messages", "session_id"),
    ("video_resources", "topic_id"),
    ("practicals", "topic_id"),
    ("practical_runs", "practical_id"),
    ("practical_runs", "learner_id"),
    ("attempts", "learner_id"),
    ("attempts", "question_id"),
    ("attempts", "assignment_id"),
    ("assignments", "school_id"),
    ("assignments", "teacher_user_id"),
    ("assignment_questions", "assignment_id"),
    ("assignment_questions", "question_id"),
    ("assignment_targets", "assignment_id"),
    ("assignment_targets", "learner_id"),
    ("attachments", "learner_id"),
    ("attachments", "session_id"),
    ("attachments", "message_id"),
    ("school_classes", "school_id"),
    ("class_members", "class_id"),
    ("class_members", "learner_id"),
    ("teaching_allocations", "school_id"),
    ("teaching_allocations", "teacher_user_id"),
    ("teaching_allocations", "subject_id"),
    ("teaching_allocations", "class_id"),
    ("staff_roles", "school_id"),
    ("staff_roles", "user_id"),
    ("staff_roles", "granted_by_user_id"),
    ("books", "subject_id"),
    ("book_pages", "book_id"),
    ("book_topic_ranges", "book_id"),
    ("book_topic_ranges", "topic_id"),
]


def _ix(table: str, column: str) -> str:
    return f"ix_{table}_{column}"


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"),
    )
    for table, column in FK_COLUMNS:
        op.execute(f'CREATE INDEX IF NOT EXISTS {_ix(table, column)} ON {table} ("{column}")')
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_teaching_allocation_whole_grade "
        "ON teaching_allocations (teacher_user_id, subject_id) WHERE class_id IS NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_teaching_allocation_whole_grade")
    for table, column in FK_COLUMNS:
        op.execute(f"DROP INDEX IF EXISTS {_ix(table, column)}")
    op.drop_column("users", "token_version")
