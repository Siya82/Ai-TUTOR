"""ADR-035: learner home language.

Revision ID: 0014
Revises: 0013
Create Date: 2026-11-19
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: Union[str, None] = "0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("learners", sa.Column("home_language", sa.String(30), nullable=True))


def downgrade() -> None:
    op.drop_column("learners", "home_language")
