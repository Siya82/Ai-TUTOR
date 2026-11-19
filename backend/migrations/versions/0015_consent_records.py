"""ADR-037 (POPIA basics): consent_records.

Revision ID: 0015
Revises: 0014
Create Date: 2026-11-19
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0015"
down_revision: Union[str, None] = "0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "consent_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("learner_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("learners.id"), nullable=False),
        sa.Column("given_by_name", sa.String(100), nullable=False),
        sa.Column("relationship_to_learner", sa.String(50), nullable=False),
        sa.Column("method", sa.String(30), nullable=False),
        sa.Column("notice_version", sa.String(20), nullable=False),
        sa.Column("recorded_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("recorded_at", sa.DateTime(), nullable=True),
        sa.Column("withdrawn_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_consent_records_learner_id", "consent_records", ["learner_id"])
    op.create_index("ix_consent_records_recorded_by_user_id", "consent_records", ["recorded_by_user_id"])


def downgrade() -> None:
    op.drop_index("ix_consent_records_recorded_by_user_id", "consent_records")
    op.drop_index("ix_consent_records_learner_id", "consent_records")
    op.drop_table("consent_records")
