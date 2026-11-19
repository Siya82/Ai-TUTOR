"""Deep scan fixes: rate events, AI usage, question reports, consent and
budget switches, test-integrity link, duplicate index.

Revision ID: 0022
Revises: 0021
Create Date: 2026-11-20
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0022"
down_revision: Union[str, None] = "0021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "rate_events",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("key", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_rate_events_key_created", "rate_events", ["key", "created_at"])

    op.create_table(
        "ai_usage",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("school_id", UUID, sa.ForeignKey("schools.id"), nullable=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("feature", sa.String(30), nullable=False),
        sa.Column("model", sa.String(80), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cache_read_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cache_write_tokens", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_ai_usage_created_at", "ai_usage", ["created_at"])
    op.create_index("ix_ai_usage_school_id", "ai_usage", ["school_id"])

    op.create_table(
        "question_reports",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("question_id", UUID, sa.ForeignKey("questions.id"), nullable=False),
        sa.Column("reported_by_user_id", UUID, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("school_id", UUID, sa.ForeignKey("schools.id"), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_question_reports_question_id", "question_reports", ["question_id"])
    op.add_column("questions", sa.Column("is_hidden", sa.Boolean(), nullable=False, server_default="false"))

    op.add_column("schools", sa.Column("require_consent", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("schools", sa.Column("ai_budget_usd_month", sa.Numeric(10, 2), nullable=True))

    op.add_column("tutor_messages", sa.Column("test_assignment_id", UUID, sa.ForeignKey("assignments.id"), nullable=True))

    # L8: learners.user_id already has a unique index (uq_learners_user_id)
    op.execute("DROP INDEX IF EXISTS ix_learners_user_id")


def downgrade() -> None:
    op.create_index("ix_learners_user_id", "learners", ["user_id"])
    op.drop_column("tutor_messages", "test_assignment_id")
    op.drop_column("schools", "ai_budget_usd_month")
    op.drop_column("schools", "require_consent")
    op.drop_column("questions", "is_hidden")
    op.drop_index("ix_question_reports_question_id", table_name="question_reports")
    op.drop_table("question_reports")
    op.drop_index("ix_ai_usage_school_id", table_name="ai_usage")
    op.drop_index("ix_ai_usage_created_at", table_name="ai_usage")
    op.drop_table("ai_usage")
    op.drop_index("ix_rate_events_key_created", table_name="rate_events")
    op.drop_table("rate_events")
