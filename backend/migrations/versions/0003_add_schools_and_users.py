"""add schools and users tables; add learners.user_id -- school-linked student login (ADR-017)

See docs/ADR-017-student-login.md. `users.student_number` is unique
only within its own school (a composite unique constraint), matching
how real school-issued student numbers work -- two different schools
will reuse the same numbers. `learners.user_id` is nullable so existing
dev data isn't forced through a migration immediately; every new
student going forward gets both rows created together by
app/services/auth.py's provision_student().

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "schools",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=True),
    )
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("role", sa.String(20), nullable=False, server_default="student"),
        sa.Column(
            "school_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("schools.id"), nullable=False
        ),
        sa.Column("student_number", sa.String(50), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("must_change_password", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime, nullable=True),
        sa.UniqueConstraint("school_id", "student_number", name="uq_user_school_student_number"),
    )
    op.add_column(
        "learners",
        sa.Column(
            "user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True
        ),
    )
    op.create_unique_constraint("uq_learners_user_id", "learners", ["user_id"])


def downgrade() -> None:
    op.drop_constraint("uq_learners_user_id", "learners", type_="unique")
    op.drop_column("learners", "user_id")
    op.drop_table("users")
    op.drop_table("schools")
