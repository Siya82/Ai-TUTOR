"""ADR-038 (CONNECT): parent links, school notices, acknowledgements.

Revision ID: 0016
Revises: 0015
Create Date: 2026-11-19
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0016"
down_revision: Union[str, None] = "0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "parent_links",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("parent_user_id", UUID, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("learner_id", UUID, sa.ForeignKey("learners.id"), nullable=False),
        sa.Column("relationship_to_learner", sa.String(50), nullable=False),
        sa.Column("created_by_user_id", UUID, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("parent_user_id", "learner_id", name="uq_parent_link"),
    )
    op.create_index("ix_parent_links_parent_user_id", "parent_links", ["parent_user_id"])
    op.create_index("ix_parent_links_learner_id", "parent_links", ["learner_id"])
    op.create_table(
        "school_notices",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("school_id", UUID, sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("grade", sa.Integer(), nullable=True),
        sa.Column("requires_ack", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_by_user_id", UUID, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_school_notices_school_id", "school_notices", ["school_id"])
    op.create_index("ix_school_notices_created_by_user_id", "school_notices", ["created_by_user_id"])
    op.create_table(
        "notice_acks",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("notice_id", UUID, sa.ForeignKey("school_notices.id"), nullable=False),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("acked_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("notice_id", "user_id", name="uq_notice_ack"),
    )
    op.create_index("ix_notice_acks_notice_id", "notice_acks", ["notice_id"])
    op.create_index("ix_notice_acks_user_id", "notice_acks", ["user_id"])


def downgrade() -> None:
    op.drop_table("notice_acks")
    op.drop_table("school_notices")
    op.drop_table("parent_links")
