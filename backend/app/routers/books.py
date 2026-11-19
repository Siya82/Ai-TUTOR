"""
E-book library API (ADR-032): list books, read a page's text, or download
just that page as a small PDF. Learners only see books at or below their
grade (ADR-026); teachers see all. Grade access is checked on every
endpoint, not only in the list.

NEW 17 Nov 2026.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_learner_or_teacher
from app.models import Book, BookPage, BookTopicRange, Learner, Subject, Topic, User
from app.schemas.books import BookDetail, BookPageOut, BookSummary, BookTopicRangeOut, SectionTitle
from app.services.epub import read_asset
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
        format=book.format,
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


@router.get("/for-topic/{topic_id}")
async def chapters_for_topic(
    topic_id: uuid.UUID,
    identity: tuple[User, Learner | None] = Depends(get_current_learner_or_teacher),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """
    NEW 19 Nov 2026 (ADR-041, textbook beside the tutor). The textbook
    chapter(s) mapped to a topic (book_topic_ranges, from the ingest), so
    the chat can open the right chapter next to the conversation. Same
    grade rule as the Library: a learner only gets books at or below
    their grade.
    """
    _, learner = identity
    stmt = (
        select(BookTopicRange, Book, Subject)
        .join(Book, BookTopicRange.book_id == Book.id)
        .join(Subject, Book.subject_id == Subject.id)
        .where(BookTopicRange.topic_id == topic_id)
        .order_by(Subject.grade.desc(), BookTopicRange.start_page)
    )
    if learner is not None:
        stmt = stmt.where(Subject.grade <= learner.grade)
    rows = (await db.execute(stmt)).all()
    out = []
    for r, book, subject in rows:
        first = (
            await db.execute(
                select(BookPage.chapter, BookPage.title).where(
                    BookPage.book_id == book.id, BookPage.page_number == r.start_page
                )
            )
        ).first()
        out.append(
            {
                "book_id": str(book.id),
                "book_title": book.title,
                "format": book.format,
                "grade": subject.grade,
                "start_page": r.start_page,
                "end_page": r.end_page,
                "chapter": (first[0] or first[1]) if first else None,
            }
        )
    # Best match first: the book for the topic's own grade, an ePub (sections
    # read better beside a chat than PDF pages), then the fullest chapter.
    out.sort(key=lambda b: (-b["grade"], b["format"] != "epub", -(b["end_page"] - b["start_page"])))
    return out


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
    sections = []
    if book.format == "epub":
        sections = [
            SectionTitle(number=n, title=t, chapter=c)
            for n, t, c in (
                await db.execute(
                    select(BookPage.page_number, BookPage.title, BookPage.chapter)
                    .where(BookPage.book_id == book.id)
                    .order_by(BookPage.page_number)
                )
            ).all()
        ]
    return BookDetail(
        **_summary(book, subject),
        source_url=book.source_url,
        sections=sections,
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
        title=page.title,
        html=page.html,
        chapter=page.chapter,
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
    if book.format != "pdf":
        raise HTTPException(status_code=404, detail="This book has no PDF pages (it's an ePub)")
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


@router.get("/{book_id}/assets")
async def book_asset(
    book_id: uuid.UUID,
    path: str = Query(..., max_length=500),
    identity: tuple[User, Learner | None] = Depends(get_current_learner_or_teacher),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """NEW (ADR-032 ePub addendum): an image from inside an ePub, by its
    path in the zip (the `data-asset` attribute the importer wrote). Only
    image types are served, and only from inside the book's own zip file --
    `path` is a zip member name, never a filesystem path."""
    book, _ = await get_readable_book(db, book_id, identity[1])
    if book.format != "epub":
        raise HTTPException(status_code=404, detail="Not found")
    file_path = BOOKS_DIR / book.file_name
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="This book's file isn't on the server yet")
    try:
        data, media_type = read_asset(file_path, path)
    except KeyError:
        raise HTTPException(status_code=404, detail="Not found")
    return Response(
        content=data,
        media_type=media_type,
        headers={"Cache-Control": "private, max-age=604800", "X-Content-Type-Options": "nosniff"},
    )
