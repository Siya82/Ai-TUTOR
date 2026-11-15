"""add learners.skip_diagnosis -- dev/admin diagnosis-redirect bypass

See docs/ADR-027-dev-admin-diagnosis-bypass.md. Siya's dev/admin test
account (student number 100001, seeded by scripts/seed_dev_data.py) has
zero real attempt history on anything, so diagnose_root_gap() (ADR-007)
always treats every topic in a chain as "unconfirmed" and redirects
teaching all the way down to the deepest prerequisite -- regardless of
which grade was actually asked about. This adds a per-learner boolean
flag (nullable=False, default false so every existing/real learner is
completely unaffected) that app/services/tutor_orchestration.py's
prepare_tutor_turn() reads to skip the redirect walk entirely for this
one account, teaching whatever topic was actually requested.

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "learners",
        sa.Column("skip_diagnosis", sa.Boolean, nullable=False, server_default="false"),
    )


def downgrade() -> None:
    op.drop_column("learners", "skip_diagnosis")
