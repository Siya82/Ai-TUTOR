"""
E-book library API (ADR-032): list books, read a page's text, or download
just that page as a small PDF. Learners only see books at or below their
grade (ADR-026); teachers see all. Grade access is checked on every
endpoint, not only in the list.

NEW 17 Nov 2026.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_learner_or_teacher
from app.models import Book, BookTopicRange, Learner, Subject, Topic, User
from app.schemas.books import BookDetail, BookPageOut, BookSummary, BookTopicRangeOut
from app.services.books import BOOKS_DIR, get_page, get_readable_book, single_page_pdf, topic_for_page

router = APIRouter(prefix="/books", tags=["books"])


def _summary(book: Book, subject: Subject) -> dict:
    return dict(
        id=book.id,
        title=book.title,
        subject_id=subject.id,
        subject_name=subject.name,
        grade=subject.grade,
        publisher=book.publisher,
        licence=book.licence,
        attribution=book.attribution,
        page_count=book.page_count,
        file_available=(BOOKS_DIR / book.file_name).exists(),
    )


@router.get("/", response_model=list[BookSummary])
async def list_books(
    identity: tuple[User, Learner | None] = Depends(get_current_learner_or_teacher),
    db: AsyncSession = Depends(get_db),
) -> list[BookSummary]:
    _, learner = identity
    stmt = select(Book, Subject).join(Subject, Book.subject_id == Subject.id)
    if learner is not None:
        stmt = stmt.where(Subject.grade <= learner.grade)
    rows = (await db.execute(stmt.order_by(Subject.grade, Subject.name, Book.title))).all()
    return [BookSummary(**_summary(b, s)) for b, s in rows]


@router.get("/{book_id}", response_model=BookDetail)
async def book_detail(
    book_id: uuid.UUID,
    identity: tuple[User, Learner | None] = Depends(get_current_learner_or_teacher),
    db: AsyncSession = Depends(get_db),
) -> BookDetail:
    book, subject = await get_readable_book(db, book_id, identity[1])
    ranges = (
        await db.execute(
            select(BookTopicRange, Topic)
            .join(Topic, BookTopicRange.topic_id == Topic.id)
            .where(BookTopicRange.book_id == book.id)
            .order_by(BookTopicRange.start_page)
        )
    ).all()
    return BookDetail(
        **_summary(book, subject),
        source_url=book.source_url,
        topic_ranges=[
            BookTopicRangeOut(topic_id=t.id, topic_name=t.name, start_page=r.start_page, end_page=r.end_page)
            for r, t in ranges
        ],
    )


@router.get("/{book_id}/pages/{page_number}", response_model=BookPageOut)
async def page_text(
    book_id: uuid.UUID,
    page_number: int,
    identity: tuple[User, Learner | None] = Depends(get_current_learner_or_teacher),
    db: AsyncSession = Depends(get_db),
) -> BookPageOut:
    book, _ = await get_readable_book(db, book_id, identity[1])
    page = await get_page(db, book, page_number)
    ranges = (
        await db.execute(select(BookTopicRange).where(BookTopicRange.book_id == book.id))
    ).scalars().all()
    match = topic_for_page(ranges, page_number)
    topic = await db.get(Topic, match.topic_id) if match else None
    return BookPageOut(
        book_id=book.id,
        page_number=page.page_number,
        page_count=book.page_count,
        text=page.text,
        has_text=bool(page.text.strip()),
        topic_id=topic.id if topic else None,
        topic_name=topic.name if topic else None,
        attribution=book.attribution,
    )


@router.get("/{book_id}/pages/{page_number}/pdf")
async def page_pdf(
    book_id: uuid.UUID,
    page_number: int,
    identity: tuple[User, Learner | None] = Depends(get_current_learner_or_teacher),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Just this one page, so a learner on mobile data downloads a page,
    not the whole book."""
    book, _ = await get_readable_book(db, book_id, identity[1])
    path = BOOKS_DIR / book.file_name
    if not path.exists():
        raise HTTPException(status_code=404, detail="This book's PDF isn't on the server yet")
    try:
        data = single_page_pdf(path, page_number)
    except IndexError:
        raise HTTPException(status_code=404, detail=f"Page {page_number} not found in this book")
    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Cache-Control": "private, max-age=86400"},
    )
