"""ADR-049: topic overview videos -- video length in seconds.

Revision ID: 0023
Revises: 0022
"""

import sqlalchemy as sa
from alembic import op

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("video_resources", sa.Column("duration_seconds", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("video_resources", "duration_seconds")
