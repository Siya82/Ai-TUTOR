"""ADR-044: ADMIN -- school profile and settings, school registration requests.

Revision ID: 0019
Revises: 0018
Create Date: 2026-11-19
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0019"
down_revision: Union[str, None] = "0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UUID = postgresql.UUID(as_uuid=True)
PROFILE = [
    ("emis_number", sa.String(20)),
    ("province", sa.String(40)),
    ("quintile", sa.Integer()),
    ("phone", sa.String(30)),
    ("email", sa.String(200)),
    ("physical_address", sa.String(300)),
]


def upgrade() -> None:
    for name, type_ in PROFILE:
        op.add_column("schools", sa.Column(name, type_, nullable=True))
    op.add_column("schools", sa.Column("parent_signup_enabled", sa.Boolean(), nullable=False, server_default="true"))
    op.add_column("schools", sa.Column("viewer_invites_enabled", sa.Boolean(), nullable=False, server_default="true"))
    op.create_table(
        "school_registrations",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("school_name", sa.String(200), nullable=False),
        sa.Column("emis_number", sa.String(20), nullable=True),
        sa.Column("province", sa.String(40), nullable=False),
        sa.Column("contact_name", sa.String(100), nullable=False),
        sa.Column("contact_role", sa.String(50), nullable=False),
        sa.Column("contact_cellphone", sa.String(20), nullable=False),
        sa.Column("contact_email", sa.String(200), nullable=True),
        sa.Column("learner_estimate", sa.Integer(), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("school_id", UUID, sa.ForeignKey("schools.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("decided_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_school_registrations_status", "school_registrations", ["status"])


def downgrade() -> None:
    op.drop_index("ix_school_registrations_status", table_name="school_registrations")
    op.drop_table("school_registrations")
    for name in ("viewer_invites_enabled", "parent_signup_enabled"):
        op.drop_column("schools", name)
    for name, _ in reversed(PROFILE):
        op.drop_column("schools", name)
