"""teaching_allocations.class_id nullable: whole-grade allocations -- ADR-031 follow-up

A NULL class means the teacher teaches that subject to the whole grade
(every learner in the school in the subject's grade), so a principal can
allocate grades and subjects before (or without) setting up classes.

Revision ID: 0012
Revises: 0011
Create Date: 2026-11-17

"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("teaching_allocations", "class_id", existing_type=postgresql.UUID(as_uuid=True), nullable=True)


def downgrade() -> None:
    op.execute("DELETE FROM teaching_allocations WHERE class_id IS NULL")
    op.alter_column("teaching_allocations", "class_id", existing_type=postgresql.UUID(as_uuid=True), nullable=False)
