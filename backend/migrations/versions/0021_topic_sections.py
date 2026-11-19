"""ADR-046: topics.section (Physics / Chemistry within Physical Sciences).

Revision ID: 0021
Revises: 0020
Create Date: 2026-11-19
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0021"
down_revision: Union[str, None] = "0020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("topics", sa.Column("section", sa.String(40), nullable=True))
    # Existing Physical Sciences topics are all physics; the seed sets the
    # chemistry ones when it adds them.
    op.execute(
        "UPDATE topics SET section = 'Physics (Paper 1)' "
        "WHERE subject_id IN (SELECT id FROM subjects WHERE name = 'Physical Sciences')"
    )


def downgrade() -> None:
    op.drop_column("topics", "section")
