"""
Load openly-licensed e-books into the Library (ADR-032).

NEW 17 Nov 2026. For each book in BOOKS whose PDF is present in
backend/content_sources/books/, this script:

  1. extracts every page's text (pypdf) and upserts the Book + BookPage rows,
  2. replaces the book's topic page ranges with the ones in the manifest,
  3. if OPENAI_API_KEY is set, embeds the pages inside mapped ranges into
     content_chunks (source "<title>, p. N") so the tutor can cite pages.
     Without the key, step 3 is skipped -- reading and "Ask THUTOra" still work.

Re-running is safe: pages are refreshed, chunks already present are skipped.

Usage (from backend/):
    python -m scripts.ingest_books                       # everything in BOOKS
    python -m scripts.ingest_books --outline everything-maths-grade-10.pdf
    python -m scripts.ingest_books --manifest my_books.json

LICENCE: use the *unbranded* Siyavula editions, which are CC-BY 3.0 (commercial
use allowed with attribution). The branded editions are CC-BY-ND. Check the
licence page inside each PDF before ingesting. Do NOT add DBE "Mind the Gap"
guides: they are non-commercial. See docs/ADR-032-ebook-library-and-reader.md.

Where to download: Siyavula's textbook pages (https://www.siyavula.com) or the
DBE's Siyavula page:
https://www.education.gov.za/Curriculum/LearningandTeachingSupportMaterials(LTSM)/SiyavulaTextbooks/tabid/591/Default.aspx
Save each PDF under backend/content_sources/books/ with the file_name below.

TOPIC RANGES: fill in "topics" as {"<seeded topic name>": [first_page, last_page]}
using page numbers as your PDF viewer shows them (1 = the first page of the
file). `--outline <file>` prints each page's first line to make this quick.
Unmapped pages are still readable; they just aren't used for page-cited answers.
"""

from __future__ import annotations

import argparse
import asyncio
import json

import httpx
from pathlib import Path

from pypdf import PdfReader
from sqlalchemy import delete, select

from app.core.database import async_session_factory
from app.models import Book, BookPage, BookTopicRange, ContentChunk, Subject, Topic
from app.services.embeddings import EmbeddingsNotConfiguredError, embed_texts
from scripts.ingest_content import chunk_text

BOOKS_DIR = Path(__file__).resolve().parent.parent / "content_sources" / "books"
EMBED_BATCH_SIZE = 32

_SIYAVULA_URL = "https://www.siyavula.com"
_MATHS = "Everything Maths Grade {g} by Siyavula and volunteers. Licensed under CC BY 3.0. " + _SIYAVULA_URL
_SCIENCE = "Everything Science Grade {g} by Siyavula and volunteers. Licensed under CC BY 3.0. " + _SIYAVULA_URL

BOOKS: list[dict] = [
    *(
        {
            "file_name": f"everything-maths-grade-{g}.pdf",
            "title": f"Everything Maths Grade {g}",
            "subject": "Pure Mathematics",
            "grade": g,
            "publisher": "Siyavula",
            "licence": "CC-BY 3.0",
            "attribution": _MATHS.format(g=g),
            "source_url": _SIYAVULA_URL,
            "topics": {},  # TODO(Siya): fill in page ranges per topic, see docstring
        }
        for g in (10, 11, 12)
    ),
    *(
        {
            "file_name": f"everything-science-grade-{g}.pdf",
            "title": f"Everything Science Grade {g}",
            "subject": "Physical Sciences",
            "grade": g,
            "publisher": "Siyavula",
            "licence": "CC-BY 3.0",
            "attribution": _SCIENCE.format(g=g),
            "source_url": _SIYAVULA_URL,
            "topics": {},  # TODO(Siya): Physics-strand topics only -- Chemistry isn't seeded
        }
        for g in (10, 11, 12)
    ),
]


# --- pure helpers (unit-tested) -------------------------------------------


def validate_ranges(topics: dict, page_count: int) -> list[str]:
    """Problems with a book's topic page ranges; empty list = fine."""
    problems = []
    for name, rng in topics.items():
        if not (isinstance(rng, (list, tuple)) and len(rng) == 2 and all(isinstance(p, int) for p in rng)):
            problems.append(f"{name!r}: range must be [first_page, last_page]")
            continue
        start, end = rng
        if start < 1 or end < start:
            problems.append(f"{name!r}: invalid range {start}-{end}")
        elif end > page_count:
            problems.append(f"{name!r}: ends on p. {end} but the PDF has {page_count} pages")
    return problems


def page_source_label(title: str, publisher: str | None, page_number: int, part: int, parts: int) -> str:
    """'Everything Maths Grade 10 (Siyavula), p. 87' -- with '#2' only if a
    page was split into several chunks. This label is what the tutor sees
    and cites (retrieval prefixes each chunk with it)."""
    who = f" ({publisher})" if publisher else ""
    suffix = f" #{part + 1}" if parts > 1 else ""
    return f"{title}{who}, p. {page_number}{suffix}"


def first_line(text: str, limit: int = 90) -> str:
    for line in text.splitlines():
        line = line.strip()
        if line:
            return line[:limit]
    return "(no text on this page)"


def extract_pages(path: Path) -> list[str]:
    reader = PdfReader(str(path))
    return [(page.extract_text() or "").strip() for page in reader.pages]


# --- DB work ----------------------------------------------------------------


async def ingest_book(session, spec: dict, embed: bool) -> None:
    path = BOOKS_DIR / spec["file_name"]
    if not path.exists():
        print(f"  SKIP (file not found): {path}")
        return

    subject = (
        await session.execute(
            select(Subject).where(Subject.name == spec["subject"], Subject.grade == spec["grade"])
        )
    ).scalar_one_or_none()
    if subject is None:
        print(f"  SKIP (subject not seeded): {spec['subject']} Gr{spec['grade']} -- run scripts.seed_dev_data first")
        return

    pages = extract_pages(path)
    problems = validate_ranges(spec.get("topics", {}), len(pages))
    if problems:
        print("  SKIP (fix the topic ranges in the manifest):")
        for p in problems:
            print(f"    - {p}")
        return

    book = (await session.execute(select(Book).where(Book.file_name == spec["file_name"]))).scalar_one_or_none()
    if book is None:
        book = Book(file_name=spec["file_name"], subject_id=subject.id, title=spec["title"], licence=spec["licence"], attribution=spec["attribution"])
        session.add(book)
    book.title = spec["title"]
    book.subject_id = subject.id
    book.publisher = spec.get("publisher")
    book.licence = spec["licence"]
    book.attribution = spec["attribution"]
    book.source_url = spec.get("source_url")
    book.page_count = len(pages)
    await session.flush()

    existing = {
        p.page_number: p
        for p in (await session.execute(select(BookPage).where(BookPage.book_id == book.id))).scalars()
    }
    empty = 0
    for number, text in enumerate(pages, start=1):
        if not text:
            empty += 1
        if number in existing:
            existing[number].text = text
        else:
            session.add(BookPage(book_id=book.id, page_number=number, text=text))
    if len(existing) > len(pages):  # the PDF got shorter: drop stale pages
        await session.execute(
            delete(BookPage).where(BookPage.book_id == book.id, BookPage.page_number > len(pages))
        )

    await session.execute(delete(BookTopicRange).where(BookTopicRange.book_id == book.id))
    ranges = []
    for topic_name, (start, end) in spec.get("topics", {}).items():
        topic = (
            await session.execute(
                select(Topic).where(Topic.subject_id == subject.id, Topic.name == topic_name)
            )
        ).scalar_one_or_none()
        if topic is None:
            print(f"  WARN: topic {topic_name!r} isn't seeded for {spec['subject']} Gr{spec['grade']} -- range ignored")
            continue
        session.add(BookTopicRange(book_id=book.id, topic_id=topic.id, start_page=start, end_page=end))
        ranges.append((topic, start, end))

    print(f"  {len(pages)} pages ({empty} with no text layer), {len(ranges)} topic range(s)")

    if not embed or not ranges:
        if ranges and not embed:
            print("  Embedding skipped (--no-embed).")
        return

    # Embed mapped pages for page-cited retrieval.
    todo: list[tuple] = []  # (topic_id, source, text)
    for topic, start, end in ranges:
        for number in range(start, end + 1):
            text = pages[number - 1]
            if not text:
                continue
            parts = chunk_text(text)
            for i, part in enumerate(parts):
                todo.append((topic.id, page_source_label(book.title, book.publisher, number, i, len(parts)), part))
    known = set(
        (await session.execute(select(ContentChunk.topic_id, ContentChunk.source).where(
            ContentChunk.source.startswith(f"{book.title}")
        ))).all()
    )
    todo = [t for t in todo if (t[0], t[1]) not in known]
    created = 0
    try:
        for i in range(0, len(todo), EMBED_BATCH_SIZE):
            batch = todo[i : i + EMBED_BATCH_SIZE]
            vectors = await embed_texts([t[2] for t in batch])
            for (topic_id, source, text), vec in zip(batch, vectors):
                session.add(ContentChunk(topic_id=topic_id, source=source, text=text, embedding=vec))
                created += 1
    except EmbeddingsNotConfiguredError:
        print("  Embedding skipped: OPENAI_API_KEY isn't set in backend/.env (reading and Ask still work).")
        return
    except httpx.HTTPError as exc:
        print(f"  Embedding failed ({exc}); {created} chunk(s) kept. Re-run later to finish.")
        return
    print(f"  {created} new page chunk(s) embedded")


async def main(args) -> None:
    if args.outline:
        path = BOOKS_DIR / args.outline
        for number, text in enumerate(extract_pages(path), start=1):
            print(f"p. {number:>4}  {first_line(text)}")
        return

    books = BOOKS
    if args.manifest:
        books = json.loads(Path(args.manifest).read_text(encoding="utf-8"))

    async with async_session_factory() as session:
        for spec in books:
            print(f"{spec['title']}  ({spec['file_name']})")
            await ingest_book(session, spec, embed=not args.no_embed)
            await session.commit()
    print("\nDone. Re-running is safe.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Load e-books into the THUTOra Library (ADR-032).")
    parser.add_argument("--outline", help="Print each page's first line for this file in content_sources/books/")
    parser.add_argument("--manifest", help="JSON file with a list of book specs, instead of BOOKS")
    parser.add_argument("--no-embed", action="store_true", help="Skip embedding even if OPENAI_API_KEY is set")
    asyncio.run(main(parser.parse_args()))
