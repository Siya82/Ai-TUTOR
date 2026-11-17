"""book_pages.chapter -- ADR-032 addendum

The chapter an ePub section belongs to (e.g. "Chapter 2: Exponents"), used
to group the reader's table of contents and to map chapters to CAPS topics.

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("book_pages", sa.Column("chapter", sa.String(300), nullable=True))


def downgrade() -> None:
    op.drop_column("book_pages", "chapter")
