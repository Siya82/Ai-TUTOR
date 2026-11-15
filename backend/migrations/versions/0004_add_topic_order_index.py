"""add topics.order_index -- fix topic ordering to follow CAPS term order, not alphabetical

See docs/BUILD_LOG.md's 15 Nov 2026 live-test entry. `GET /topics` was
ordering by `Topic.name`, so the sidebar showed topics alphabetically
within a subject instead of the term-by-term order every
seed_dev_data.py topic list is already written in (and every
subject-addition ADR documents as the real DBE ATP order). This adds
an explicit `order_index` column (nullable=False, default 0 so
existing rows aren't broken before the next seed run) that
seed_dev_data.py now sets/refreshes for every topic on every run.

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "topics",
        sa.Column("order_index", sa.Integer, nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("topics", "order_index")
