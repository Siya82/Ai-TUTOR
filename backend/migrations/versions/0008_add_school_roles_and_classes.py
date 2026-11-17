"""add classes, class members, teaching allocations, staff roles, users.display_name -- ADR-031

See docs/ADR-031-school-roles-and-scoping.md. Every staff account used to
see every learner in its school. Access is now resolved from teaching
allocations (subject + class) and staff roles (principal, deputy
principal, departmental head, school admin).

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.add_column("users", sa.Column("display_name", sa.String(100), nullable=True))

    op.create_table(
        "school_classes",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("school_id", UUID, sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("grade", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=True),
        sa.UniqueConstraint("school_id", "name", name="uq_school_class_name"),
    )
    op.create_table(
        "class_members",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("class_id", UUID, sa.ForeignKey("school_classes.id"), nullable=False),
        sa.Column("learner_id", UUID, sa.ForeignKey("learners.id"), nullable=False),
        sa.UniqueConstraint("class_id", "learner_id", name="uq_class_member"),
    )
    op.create_table(
        "teaching_allocations",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("school_id", UUID, sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("teacher_user_id", UUID, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("subject_id", UUID, sa.ForeignKey("subjects.id"), nullable=False),
        sa.Column("class_id", UUID, sa.ForeignKey("school_classes.id"), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=True),
        sa.UniqueConstraint("teacher_user_id", "subject_id", "class_id", name="uq_teaching_allocation"),
    )
    op.create_table(
        "staff_roles",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("school_id", UUID, sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("role", sa.String(30), nullable=False),
        sa.Column("subject_name", sa.String(100), nullable=True),
        sa.Column("grade", sa.Integer, nullable=True),
        sa.Column("granted_by_user_id", UUID, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=True),
    )
    op.create_index("ix_class_members_learner_id", "class_members", ["learner_id"])
    op.create_index("ix_teaching_allocations_teacher", "teaching_allocations", ["teacher_user_id"])
    op.create_index("ix_staff_roles_user_id", "staff_roles", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_staff_roles_user_id", table_name="staff_roles")
    op.drop_index("ix_teaching_allocations_teacher", table_name="teaching_allocations")
    op.drop_index("ix_class_members_learner_id", table_name="class_members")
    op.drop_table("staff_roles")
    op.drop_table("teaching_allocations")
    op.drop_table("class_members")
    op.drop_table("school_classes")
    op.drop_column("users", "display_name")
