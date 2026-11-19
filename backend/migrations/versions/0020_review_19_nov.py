"""Code review 19 Nov 2026: teacher mark overrides, audit log.

Revision ID: 0020
Revises: 0019
Create Date: 2026-11-19
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0020"
down_revision: Union[str, None] = "0019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    # #2: teacher corrects an AI mark
    op.add_column("attempts", sa.Column("teacher_note", sa.Text(), nullable=True))
    op.add_column("attempts", sa.Column("marked_by_user_id", UUID, sa.ForeignKey("users.id"), nullable=True))
    op.add_column("attempts", sa.Column("marked_at", sa.DateTime(), nullable=True))
    # #7: close an assignment early
    op.add_column("assignments", sa.Column("closed_at", sa.DateTime(), nullable=True))
    # #11: audit trail
    op.create_table(
        "audit_events",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("school_id", UUID, sa.ForeignKey("schools.id"), nullable=True),
        sa.Column("actor_user_id", UUID, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("target_type", sa.String(30), nullable=True),
        sa.Column("target_id", sa.String(64), nullable=True),
        sa.Column("details", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_audit_events_school_id", "audit_events", ["school_id"])
    op.create_index("ix_audit_events_created_at", "audit_events", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_audit_events_created_at", table_name="audit_events")
    op.drop_index("ix_audit_events_school_id", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_column("assignments", "closed_at")
    op.drop_column("attempts", "marked_at")
    op.drop_column("attempts", "marked_by_user_id")
    op.drop_column("attempts", "teacher_note")
