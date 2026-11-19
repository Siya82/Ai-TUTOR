"""ADR-043: guardian contacts, parent self-sign-up codes, viewers.

Revision ID: 0018
Revises: 0017
Create Date: 2026-11-19
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0018"
down_revision: Union[str, None] = "0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.add_column("parent_links", sa.Column("kind", sa.String(20), nullable=False, server_default="guardian"))
    op.add_column("parent_links", sa.Column("invited_by_user_id", UUID, sa.ForeignKey("users.id"), nullable=True))
    op.create_table(
        "learner_guardians",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("learner_id", UUID, sa.ForeignKey("learners.id"), nullable=False),
        sa.Column("full_name", sa.String(100), nullable=False),
        sa.Column("relationship_to_learner", sa.String(50), nullable=False),
        sa.Column("cellphone", sa.String(20), nullable=True),
        sa.Column("email", sa.String(200), nullable=True),
        sa.Column("parent_user_id", UUID, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_by_user_id", UUID, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    for col in ("learner_id", "cellphone", "parent_user_id"):
        op.create_index(f"ix_learner_guardians_{col}", "learner_guardians", [col])
    op.create_table(
        "signup_codes",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("school_id", UUID, sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("cellphone", sa.String(20), nullable=False),
        sa.Column("code_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_signup_codes_school_id", "signup_codes", ["school_id"])
    op.create_index("ix_signup_codes_cellphone", "signup_codes", ["cellphone"])
    op.create_table(
        "viewer_invites",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("school_id", UUID, sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("learner_id", UUID, sa.ForeignKey("learners.id"), nullable=False),
        sa.Column("invited_by_user_id", UUID, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("viewer_name", sa.String(100), nullable=False),
        sa.Column("relationship_to_learner", sa.String(50), nullable=False),
        sa.Column("code_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    for col in ("school_id", "learner_id", "invited_by_user_id", "code_hash"):
        op.create_index(f"ix_viewer_invites_{col}", "viewer_invites", [col])


def downgrade() -> None:
    op.drop_table("viewer_invites")
    op.drop_table("signup_codes")
    op.drop_table("learner_guardians")
    op.drop_column("parent_links", "invited_by_user_id")
    op.drop_column("parent_links", "kind")
