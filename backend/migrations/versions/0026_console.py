"""ADR-051: THUTOra Console -- Zynora staff accounts, and who-did-it columns.

Revision ID: 0026
Revises: 0025
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "console_staff",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(200), nullable=False, unique=True),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("totp_secret", sa.String(64), nullable=True),
        sa.Column("totp_confirmed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("totp_last_step", sa.BigInteger(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_login_at", sa.DateTime(), nullable=True),
    )
    op.add_column("audit_events", sa.Column("console_staff_id", UUID(as_uuid=True), sa.ForeignKey("console_staff.id"), nullable=True))
    op.create_index("ix_audit_events_console_staff_id", "audit_events", ["console_staff_id"])
    op.add_column("support_messages", sa.Column("console_staff_id", UUID(as_uuid=True), sa.ForeignKey("console_staff.id"), nullable=True))


def downgrade() -> None:
    op.drop_column("support_messages", "console_staff_id")
    op.drop_index("ix_audit_events_console_staff_id", table_name="audit_events")
    op.drop_column("audit_events", "console_staff_id")
    op.drop_table("console_staff")
