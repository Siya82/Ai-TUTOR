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

LICENCE: use the *unbranded* Siyavula editions (CC BY), which Siyavula ships as
ePub. Its PDFs are the branded CC BY-ND editions, and this script refuses
them: it reads each book's own licence statement and only imports CC BY /
CC BY-SA (see licence_decision()). Do NOT add DBE "Mind the Gap"
guides: they are non-commercial. See docs/ADR-032-ebook-library-and-reader.md.

Where to download: Siyavula's textbook pages (https://www.siyavula.com) or the
DBE's Siyavula page:
https://www.education.gov.za/Curriculum/LearningandTeachingSupportMaterials(LTSM)/SiyavulaTextbooks/tabid/591/Default.aspx
Save each PDF under backend/content_sources/books/ with the file_name below.

TOPICS: each book maps seeded topic names to the book's chapter titles
(ePubs), or to [first, last] page numbers (PDFs). `--outline <file>` lists
the chapters and sections.
Unmapped pages are still readable; they just aren't used for page-cited answers.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re

import httpx
from pathlib import Path

from pypdf import PdfReader
from sqlalchemy import delete, select

from app.core.database import async_session_factory
from app.models import Book, BookPage, BookTopicRange, ContentChunk, Subject, Topic
from app.services.embeddings import EmbeddingsNotConfiguredError, embed_texts
from app.services.epub import COMMERCIAL_ADAPTABLE, detect_licence, licence_family, parse_epub
from scripts.ingest_content import chunk_text

BOOKS_DIR = Path(__file__).resolve().parent.parent / "content_sources" / "books"
EMBED_BATCH_SIZE = 32

_SIYAVULA_URL = "https://www.siyavula.com"
# UPDATED 17 Nov 2026 (ADR-032 ePub addendum): Siyavula's downloadable PDFs
# turned out to be the branded CC BY-ND editions; the CC BY (unbranded)
# editions are ePubs. So the manifest now lists .epub files, and the licence
# + attribution are taken from the book itself at import time ({licence}).
_ATTRIBUTION = "{title} by Siyavula Education and volunteers. Licensed under {licence}. " + _SIYAVULA_URL

def _siyavula(file_name: str, title: str, subject: str, grade: int, topics: dict) -> dict:
    return {
        "file_name": file_name,
        "title": title,
        "subject": subject,
        "grade": grade,
        "publisher": "Siyavula",
        "licence": "CC BY",  # expected; the book's own licence statement wins
        "attribution": _ATTRIBUTION,
        "source_url": _SIYAVULA_URL,
        "topics": topics,
    }


# Topic -> the book's chapter title(s) that teach it (matched case-insensitively,
# without the "Chapter N:" prefix). Checked against the real Siyavula CC BY
# ePubs on 17 Nov 2026. Chapters with no seeded CAPS topic (e.g. Grade 11
# "Linear programming", every Chemistry chapter) are simply left unmapped:
# still readable, just not tied to a tutor topic.
BOOKS: list[dict] = [
    _siyavula("everything-maths-grade-10.epub", "Everything Maths Grade 10", "Pure Mathematics", 10, {
        "Algebraic Expressions": ["Algebraic expressions"],
        "Exponents": ["Exponents"],
        "Number Patterns": ["Number patterns"],
        "Equations and Inequalities": ["Equations and inequalities"],
        "Trigonometry": ["Trigonometry"],  # chapters 5 and 11
        "Functions": ["Functions"],
        "Euclidean Geometry": ["Euclidean geometry"],  # chapters 7 and 12
        "Analytical Geometry": ["Analytical geometry"],
        "Finance, Growth and Decay": ["Finance and growth"],
        "Statistics": ["Statistics"],
        "Measurement": ["Measurements"],
        "Probability": ["Probability"],
    }),
    _siyavula("everything-maths-grade-11.epub", "Everything Maths Grade 11", "Pure Mathematics", 11, {
        "Exponents and Surds": ["Exponents and surds"],
        "Equations and Inequalities": ["Equations and inequalities"],
        "Number Patterns": ["Number patterns"],
        "Analytical Geometry": ["Analytical geometry"],
        "Functions": ["Functions"],
        "Trigonometry": ["Trigonometry"],
        "Measurement": ["Measurement"],
        "Euclidean Geometry": ["Euclidean geometry"],
        "Finance, Growth and Decay": ["Finance, growth and decay"],
        "Probability": ["Probability"],
        "Statistics": ["Statistics"],
    }),
    _siyavula("everything-maths-grade-12.epub", "Everything Maths Grade 12", "Pure Mathematics", 12, {
        "Sequences and Series": ["Sequences and series"],
        "Functions and Inverse Functions": ["Functions"],
        "Exponential and Logarithmic Functions": ["Functions"],  # logs are taught in the Functions chapter
        "Finance, Growth and Decay": ["Finance"],
        "Trigonometry: Compound Angles": ["Trigonometry"],
        "Trigonometry: 2D and 3D Problems": ["Trigonometry"],
        "Polynomials": ["Polynomials"],
        "Differential Calculus": ["Differential calculus"],
        "Analytical Geometry": ["Analytical geometry"],
        "Euclidean Geometry": ["Euclidean geometry"],
        "Statistics: Regression and Correlation": ["Statistics"],
        "Counting and Probability": ["Probability"],
    }),
    _siyavula("everything-science-grade-10.epub", "Everything Science Grade 10", "Physical Sciences", 10, {
        "Vectors in Two Dimensions": ["Vectors and scalars"],
        "Motion in One Dimension": ["Motion in one dimension"],
        "Mechanical Energy": ["Mechanical energy"],
        "Waves, Sound and Light": ["Transverse pulses", "Transverse waves", "Longitudinal waves", "Sound"],
        "Electromagnetic Radiation": ["Electromagnetic radiation"],
        "Magnetism": ["Magnetism"],
        "Electrostatics": ["Electrostatics"],
        "Electric Circuits": ["Electric circuits"],
    }),
    _siyavula("everything-science-grade-11.epub", "Everything Science Grade 11", "Physical Sciences", 11, {
        "Vectors in Two Dimensions": ["Vectors in two dimensions"],
        "Newton's Laws": ["Newton's laws"],
        "Newton's Universal Law of Gravitation": ["Newton's laws"],  # taught inside that chapter
        "Electrostatics": ["Electrostatics"],
        "Electromagnetism": ["Electromagnetism"],
        "Electric Circuits": ["Electric circuits"],
    }),
    _siyavula("everything-science-grade-12.epub", "Everything Science Grade 12", "Physical Sciences", 12, {
        "Momentum and Impulse": ["Momentum and impulse"],
        "Vertical Projectile Motion": ["Vertical projectile motion in one dimension"],
        "Work, Energy and Power": ["Work, energy and power"],
        "Doppler Effect": ["Doppler effect"],
        "Electric Circuits": ["Electric circuits"],
        "Electrodynamics": ["Electrodynamics"],
        "Photoelectric Effect": ["Optical phenomena and properties of matter"],
    }),
]


# --- pure helpers (unit-tested) -------------------------------------------


_CHAPTER_PREFIX = re.compile(r"^\s*chapter\s+\d+\s*:\s*", re.I)


def chapter_key(chapter: str | None) -> str:
    """'Chapter 2: Exponents' -> 'exponents' (also normalises curly quotes)."""
    if not chapter:
        return ""
    name = _CHAPTER_PREFIX.sub("", chapter).replace("\u2019", "'").strip().lower()
    return re.sub(r"\s+", " ", name)


def chapter_runs(section_chapters: list[str | None]) -> dict[str, list[tuple[int, int]]]:
    """{chapter key: [(first, last), ...]} over 1-based section numbers.
    A chapter that appears twice (Grade 10 Trigonometry, chapters 5 and 11)
    gets two runs."""
    runs: dict[str, list[tuple[int, int]]] = {}
    prev, start = None, 1
    for i, ch in enumerate(section_chapters + [object()], start=1):
        key = chapter_key(ch) if isinstance(ch, (str, type(None))) else None
        if key != prev:
            if prev:
                runs.setdefault(prev, []).append((start, i - 1))
            prev, start = key, i
    return runs


def resolve_topic_ranges(topics: dict, section_chapters: list[str | None]) -> tuple[list[tuple[str, int, int]], list[str]]:
    """Manifest topics -> [(topic name, first, last)], plus problems.
    A value is either [first, last] (page/section numbers) or a list of
    chapter titles (ePubs)."""
    out, problems = [], []
    runs = chapter_runs(section_chapters)
    for name, value in topics.items():
        if isinstance(value, (list, tuple)) and value and all(isinstance(v, str) for v in value):
            for chapter in value:
                found = runs.get(chapter_key(chapter))
                if not found:
                    problems.append(f"{name!r}: no chapter called {chapter!r} in this book")
                    continue
                out.extend((name, a, b) for a, b in found)
        else:
            bad = validate_ranges({name: value}, len(section_chapters))
            if bad:
                problems.extend(bad)
            else:
                out.append((name, value[0], value[1]))
    return out, problems


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


def section_source_label(title: str, publisher: str | None, section_title: str, part: int, parts: int) -> str:
    """ePub sections have no page numbers: cite the section heading instead,
    e.g. 'Everything Maths Grade 10 (Siyavula), section "Laws of exponents"'."""
    who = f" ({publisher})" if publisher else ""
    suffix = f" #{part + 1}" if parts > 1 else ""
    return f'{title}{who}, section "{section_title}"{suffix}'


def first_line(text: str, limit: int = 90) -> str:
    for line in text.splitlines():
        line = line.strip()
        if line:
            return line[:limit]
    return "(no text on this page)"


def extract_pages(path: Path) -> list[str]:
    reader = PdfReader(str(path))
    return [(page.extract_text() or "").strip() for page in reader.pages]


def licence_decision(detected: str | None, expected: str, allow_restricted: bool) -> tuple[str | None, str]:
    """(licence to store, message). licence None = don't import.

    ADR-032: THUTOra is commercial and generates explanations from the text,
    so only licences that allow commercial use AND adaptation (CC BY, CC BY-SA)
    are imported. A restrictive licence (ND/NC) is refused unless
    --allow-restricted is passed for local testing. If no licence statement
    can be found, the manifest's expected licence is used with a warning."""
    if detected is None:
        return expected, f"WARNING: no licence statement found in the book; using the manifest's {expected!r}. Check it by hand."
    family = licence_family(detected)
    if family in COMMERCIAL_ADAPTABLE:
        return detected, f"Licence: {detected}"
    if allow_restricted:
        return detected, f"Licence: {detected} -- RESTRICTED, imported only because of --allow-restricted (local testing only)"
    return None, (
        f"SKIP: this file is licensed {detected}, which doesn't allow THUTOra's use "
        "(ADR-032). Use the CC BY (unbranded) edition instead."
    )


# --- DB work ----------------------------------------------------------------


async def ingest_book(session, spec: dict, embed: bool, allow_restricted: bool = False) -> None:
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

    is_epub = path.suffix.lower() == ".epub"
    if is_epub:
        parsed = parse_epub(path)
        pages = [sec.text for sec in parsed.sections]
        page_titles = [sec.title for sec in parsed.sections]
        page_html = [sec.html for sec in parsed.sections]
        page_chapters = [sec.chapter for sec in parsed.sections]
        detected = parsed.licence
    else:
        pages = extract_pages(path)
        page_titles = [None] * len(pages)
        page_html = [None] * len(pages)
        page_chapters = [None] * len(pages)
        detected = detect_licence("\n".join(pages[:12]))
    licence, message = licence_decision(detected, spec["licence"], allow_restricted)
    print(f"  {message}")
    if licence is None:
        return
    wanted_ranges, problems = resolve_topic_ranges(spec.get("topics", {}), page_chapters)
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
    book.licence = licence
    book.attribution = spec["attribution"].format(title=spec["title"], licence=licence)
    book.format = "epub" if is_epub else "pdf"
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
        title, html, chapter = page_titles[number - 1], page_html[number - 1], page_chapters[number - 1]
        if number in existing:
            existing[number].text = text
            existing[number].title = title
            existing[number].html = html
            existing[number].chapter = chapter
        else:
            session.add(BookPage(book_id=book.id, page_number=number, text=text, title=title, html=html, chapter=chapter))
    if len(existing) > len(pages):  # the PDF got shorter: drop stale pages
        await session.execute(
            delete(BookPage).where(BookPage.book_id == book.id, BookPage.page_number > len(pages))
        )

    await session.execute(delete(BookTopicRange).where(BookTopicRange.book_id == book.id))
    ranges = []
    for topic_name, start, end in wanted_ranges:
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

    unit = "sections" if is_epub else "pages"
    print(f"  {len(pages)} {unit} ({empty} with no text), {len(ranges)} topic range(s)")

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
                label = (
                    section_source_label(book.title, book.publisher, page_titles[number - 1], i, len(parts))
                    if is_epub
                    else page_source_label(book.title, book.publisher, number, i, len(parts))
                )
                todo.append((topic.id, label, part))
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
        if path.suffix.lower() == ".epub":
            parsed = parse_epub(path)
            print(f"{parsed.title}  --  licence found: {parsed.licence or 'none'}")
            current = object()
            for number, sec in enumerate(parsed.sections, start=1):
                if sec.chapter != current:
                    current = sec.chapter
                    print(f"\n== {sec.chapter or '(front matter)'}")
                print(f"§ {number:>4}  {sec.title[:70]}  ({len(sec.text)} chars, {sec.equations} eq)")
        else:
            pages = extract_pages(path)
            print(f"licence found: {detect_licence(chr(10).join(pages[:12])) or 'none'}")
            for number, text in enumerate(pages, start=1):
                print(f"p. {number:>4}  {first_line(text)}")
        return

    books = BOOKS
    if args.manifest:
        books = json.loads(Path(args.manifest).read_text(encoding="utf-8"))

    async with async_session_factory() as session:
        for spec in books:
            print(f"{spec['title']}  ({spec['file_name']})")
            await ingest_book(session, spec, embed=not args.no_embed, allow_restricted=args.allow_restricted)
            await session.commit()
    print("\nDone. Re-running is safe.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Load e-books into the THUTOra Library (ADR-032).")
    parser.add_argument("--outline", help="Print each page's first line for this file in content_sources/books/")
    parser.add_argument("--manifest", help="JSON file with a list of book specs, instead of BOOKS")
    parser.add_argument("--no-embed", action="store_true", help="Skip embedding even if OPENAI_API_KEY is set")
    parser.add_argument(
        "--allow-restricted",
        action="store_true",
        help="LOCAL TESTING ONLY: import a CC BY-ND/NC book anyway (ADR-032 forbids it in production)",
    )
    asyncio.run(main(parser.parse_args()))
