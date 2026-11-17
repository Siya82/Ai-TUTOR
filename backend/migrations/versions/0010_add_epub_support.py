"""ePub support for the e-book library -- ADR-032 addendum

books.format ("pdf" | "epub"); book_pages.title and book_pages.html for
ePub sections (an ePub has no printed pages, so it is split into sections
at headings and each section is stored as a BookPage).

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("books", sa.Column("format", sa.String(10), nullable=False, server_default="pdf"))
    op.add_column("book_pages", sa.Column("title", sa.String(300), nullable=True))
    op.add_column("book_pages", sa.Column("html", sa.Text, nullable=True))


def downgrade() -> None:
    op.drop_column("book_pages", "html")
    op.drop_column("book_pages", "title")
    op.drop_column("books", "format")
