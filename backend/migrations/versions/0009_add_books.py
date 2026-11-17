"""add books, book_pages, book_topic_ranges -- ADR-032

See docs/ADR-032-ebook-library-and-reader.md. Openly-licensed textbooks
(Siyavula CC-BY editions) a learner can read page by page and ask the
tutor about.

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "books",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("subject_id", UUID, sa.ForeignKey("subjects.id"), nullable=False),
        sa.Column("publisher", sa.String(100), nullable=True),
        sa.Column("licence", sa.String(50), nullable=False),
        sa.Column("attribution", sa.Text, nullable=False),
        sa.Column("source_url", sa.String(500), nullable=True),
        sa.Column("file_name", sa.String(255), nullable=False, unique=True),
        sa.Column("page_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime, nullable=True),
    )
    op.create_table(
        "book_pages",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("book_id", UUID, sa.ForeignKey("books.id"), nullable=False),
        sa.Column("page_number", sa.Integer, nullable=False),
        sa.Column("text", sa.Text, nullable=False, server_default=""),
        sa.UniqueConstraint("book_id", "page_number", name="uq_book_page"),
    )
    op.create_table(
        "book_topic_ranges",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("book_id", UUID, sa.ForeignKey("books.id"), nullable=False),
        sa.Column("topic_id", UUID, sa.ForeignKey("topics.id"), nullable=False),
        sa.Column("start_page", sa.Integer, nullable=False),
        sa.Column("end_page", sa.Integer, nullable=False),
    )
    op.create_index("ix_book_topic_ranges_book_id", "book_topic_ranges", ["book_id"])


def downgrade() -> None:
    op.drop_index("ix_book_topic_ranges_book_id", table_name="book_topic_ranges")
    op.drop_table("book_topic_ranges")
    op.drop_table("book_pages")
    op.drop_table("books")
