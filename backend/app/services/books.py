"""
E-book library helpers (ADR-032). Pure functions are unit-tested; the
async ones are shared by routers/books.py and routers/tutor.py so both
apply the same grade rule and the same page lookup.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Optional

from fastapi import HTTPException
from pypdf import PdfReader, PdfWriter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Book, BookPage, BookTopicRange, Learner, Subject

BOOKS_DIR = Path(__file__).resolve().parent.parent.parent / "content_sources" / "books"

# How much of a page / a highlight is sent to the tutor. A textbook page is
# typically 1-3k characters; the cap stops a pathological page (or a
# client-sent selection) from blowing up the prompt.
MAX_PAGE_CHARS = 6000
MAX_SELECTION_CHARS = 1500


def topic_for_page(ranges: list[BookTopicRange], page_number: int) -> Optional[BookTopicRange]:
    """The (first) mapped range containing this page, or None."""
    for r in sorted(ranges, key=lambda r: (r.start_page, r.end_page)):
        if r.start_page <= page_number <= r.end_page:
            return r
    return None


def location_label(page_number: int, section_title: Optional[str] = None) -> str:
    """'p. 87' for a PDF page; 'the section "Laws of exponents"' for an ePub
    section (ePubs have no printed page numbers)."""
    return f'the section "{section_title}"' if section_title else f"p. {page_number}"


def build_book_passage(
    *,
    title: str,
    page_number: int,
    page_text: str,
    selected_text: Optional[str],
    attribution: str,
    section_title: Optional[str] = None,
) -> str:
    """The text block put in front of the learner's question for one turn."""
    page_text = (page_text or "").strip()
    if len(page_text) > MAX_PAGE_CHARS:
        page_text = page_text[:MAX_PAGE_CHARS] + " [...]"
    where = location_label(page_number, section_title)
    unit = "Section" if section_title else "Page"
    lines = [
        f'[The learner is reading "{title}", {where}, and is asking about it. '
        f"Explain using it where it helps, refer to it as {where}, and don't "
        f"just restate it -- teach. Source: {attribution}]",
        "",
        f"--- {unit}: {section_title or page_number} ---",
        page_text or "(This page has no extractable text -- it may be a scanned image or diagram.)",
        f"--- end of {unit.lower()} ---",
    ]
    if selected_text and selected_text.strip():
        sel = selected_text.strip()[:MAX_SELECTION_CHARS]
        lines += ["", f'The learner highlighted: "{sel}"']
    return "\n".join(lines)


def book_history_summary(
    title: str, page_number: int, selected_text: Optional[str], section_title: Optional[str] = None
) -> str:
    """What gets stored in chat history instead of the whole page."""
    base = f"(Reading {title}, {location_label(page_number, section_title)}"
    if selected_text and selected_text.strip():
        sel = " ".join(selected_text.split())
        sel = sel if len(sel) <= 80 else sel[:80] + "…"
        base += f'; highlighted "{sel}"'
    return base + ")"


def single_page_pdf(path: Path, page_number: int) -> bytes:
    """Cut one page out of a book PDF -- what the reader downloads."""
    reader = PdfReader(str(path))
    if not 1 <= page_number <= len(reader.pages):
        raise IndexError(page_number)
    writer = PdfWriter()
    writer.add_page(reader.pages[page_number - 1])
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


async def get_readable_book(db: AsyncSession, book_id, learner: Optional[Learner]) -> tuple[Book, Subject]:
    """404 if missing; 403 if above the learner's grade (ADR-026 rule).
    `learner=None` means a teacher, who may read any book."""
    row = (
        await db.execute(select(Book, Subject).join(Subject, Book.subject_id == Subject.id).where(Book.id == book_id))
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Book not found")
    book, subject = row
    if learner is not None and subject.grade > learner.grade:
        raise HTTPException(status_code=403, detail="This book is above your current grade.")
    return book, subject


async def get_page(db: AsyncSession, book: Book, page_number: int) -> BookPage:
    page = (
        await db.execute(
            select(BookPage).where(BookPage.book_id == book.id, BookPage.page_number == page_number)
        )
    ).scalar_one_or_none()
    if page is None:
        raise HTTPException(status_code=404, detail=f"Page {page_number} not found in this book")
    return page
