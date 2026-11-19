"""ADR-039 (INSIGHTS): districts, circuits, offices, official assignments.

Revision ID: 0017
Revises: 0016
Create Date: 2026-11-19
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0017"
down_revision: Union[str, None] = "0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "districts",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("province", sa.String(60), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "circuits",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("district_id", UUID, sa.ForeignKey("districts.id"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_circuits_district_id", "circuits", ["district_id"])
    op.add_column("schools", sa.Column("kind", sa.String(20), nullable=False, server_default="school"))
    op.add_column("schools", sa.Column("circuit_id", UUID, sa.ForeignKey("circuits.id"), nullable=True))
    op.create_index("ix_schools_circuit_id", "schools", ["circuit_id"])
    op.create_table(
        "official_assignments",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("district_id", UUID, sa.ForeignKey("districts.id"), nullable=True),
        sa.Column("circuit_id", UUID, sa.ForeignKey("circuits.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "(district_id IS NULL) <> (circuit_id IS NULL)", name="ck_official_one_level"
        ),
    )
    op.create_index("ix_official_assignments_user_id", "official_assignments", ["user_id"])
    op.create_index("ix_official_assignments_district_id", "official_assignments", ["district_id"])
    op.create_index("ix_official_assignments_circuit_id", "official_assignments", ["circuit_id"])


def downgrade() -> None:
    op.drop_table("official_assignments")
    op.drop_index("ix_schools_circuit_id", "schools")
    op.drop_column("schools", "circuit_id")
    op.drop_column("schools", "kind")
    op.drop_table("circuits")
    op.drop_table("districts")
