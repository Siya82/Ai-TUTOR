"""add attachments table -- student file uploads (image/pdf/docx)

See docs/ADR-016-student-file-attachments.md. session_id/message_id are
nullable because an attachment is uploaded via its own endpoint before
the student's message (and therefore its session/message) exists --
both get backfilled by POST /tutor/message once it creates the
resulting TutorMessage row.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "attachments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("learner_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("learners.id"), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tutor_sessions.id"), nullable=True),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tutor_messages.id"), nullable=True),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("storage_path", sa.String(500), nullable=False),
        sa.Column("extracted_text", sa.Text, nullable=True),
        sa.Column("extraction_warning", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=True),
    )


def downgrade() -> None:
    op.drop_table("attachments")
