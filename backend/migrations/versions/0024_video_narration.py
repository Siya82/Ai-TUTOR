"""ADR-049: record whether a topic video has a voice-over, so LEARN shows
the voice on/off switch only where there's a voice to switch.

Revision ID: 0024
Revises: 0023
"""

import sqlalchemy as sa
from alembic import op

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "video_resources",
        sa.Column("has_narration", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("video_resources", "has_narration")
