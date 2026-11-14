"""
Real RAG content-ingestion pipeline (ADR-021) -- the first actual
implementation of the long-deferred placeholder described in
REBUILD_SPEC.md Section 8 and scripts/seed_dev_data.py's own
PLACEHOLDER_EMBEDDING / ensure_placeholder_content_chunk().

Motivated by a real, confirmed isiZulu Home Language accuracy failure:
a live-tested matching exercise ("Qondanisa uHlu A noHlu B") where the
tutor got some matches wrong. Grounds isiZulu (and, for parity,
English) Home Language Grade 10 against the official DBE 2023 November
Grade 12 NSC Home Language papers -- the closest clean, centrally-
published source (Grade 10 papers are not centrally published; see
docs/ADR-021-rag-content-ingestion.md for the sourcing reasoning and
its explicit limits).

THIS SCRIPT DOES NOT FABRICATE SOURCE TEXT. It reads real local PDF/
text files you place under backend/content_sources/ -- it does not (and
must not) invent isiZulu content itself, which would recreate the exact
unverified-content risk ADR-021 exists to reduce. See MANIFEST below
for exactly which files it expects, and where to download them from.

Run from backend/, with the venv active, Docker Postgres up, and
OPENAI_API_KEY set in backend/.env:
    python -m scripts.ingest_content

Safe to re-run: each chunk is looked up by its own (topic_id, source)
natural key (source includes a stable per-chunk index) before being
created -- same idempotency discipline as seed_dev_data.py. A file
listed in MANIFEST that hasn't been downloaded yet is skipped with a
clear message, not an error, so re-running after seeding more topics
or downloading more files just picks up the rest.
"""

import asyncio
import re
from pathlib import Path

from pypdf import PdfReader
from sqlalchemy import select

from app.core.database import async_session_factory
from app.models import ContentChunk, Subject, Topic
from app.services.embeddings import embed_texts

CONTENT_SOURCES_DIR = Path(__file__).resolve().parent.parent / "content_sources"

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150
EMBED_BATCH_SIZE = 50

# --- Manifest: which local source file grounds which existing Topic ---
#
# Each entry: (relative path under content_sources/, subject_name, grade,
# topic_name, source_label). source_label is what ends up in
# ContentChunk.source and in the tutor's grounding block -- keep it
# short and identifiable (which paper/memo it came from).
#
# These six PDFs are NOT included in this repo -- past-paper
# redistribution rights aren't clearly established (see ADR-021's open
# licensing note) -- download them yourself from the official DBE
# portal and save them under backend/content_sources/ using these exact
# filenames:
#
#   isizulu_hl_2023_nov_paper1.pdf        (Language in Context, 70 marks)
#     https://www.education.gov.za/LinkClick.aspx?fileticket=BfP-rQiQs-E%3d&tabid=4682&portalid=0&mid=12651
#   isizulu_hl_2023_nov_paper1_memo.pdf
#     https://www.education.gov.za/LinkClick.aspx?fileticket=EVNdCRXqH64%3d&tabid=4682&portalid=0&mid=12651
#   isizulu_hl_2023_nov_paper2.pdf        (Literature, 80 marks)
#     https://www.education.gov.za/LinkClick.aspx?fileticket=-gtiQUc_iws%3d&tabid=4682&portalid=0&mid=12651
#   isizulu_hl_2023_nov_paper2_memo.pdf
#     https://www.education.gov.za/LinkClick.aspx?fileticket=IE6dyOusrzs%3d&tabid=4682&portalid=0&mid=12651
#   isizulu_hl_2023_nov_paper3.pdf        (Writing)
#     https://www.education.gov.za/LinkClick.aspx?fileticket=sIjTCbBClmM%3d&tabid=4682&portalid=0&mid=12651
#   isizulu_hl_2023_nov_paper3_memo.pdf
#     https://www.education.gov.za/LinkClick.aspx?fileticket=fF-m2kxtt-I%3d&tabid=4682&portalid=0&mid=12651
#
# All six share &tabid=4682&portalid=0&mid=12651. English HL equivalents
# for the same 2023 November sitting are not yet sourced -- add them to
# this manifest the same way once found (see Open items in ADR-021).
MANIFEST: list[tuple[str, str, int, str, str]] = [
    (
        "isizulu_hl_2023_nov_paper1.pdf",
        "isiZulu Home Language",
        10,
        "Language Structures and Conventions",
        "DBE NSC 2023 Nov Paper 1 (Gr12, off-grade grounding)",
    ),
    (
        "isizulu_hl_2023_nov_paper1_memo.pdf",
        "isiZulu Home Language",
        10,
        "Language Structures and Conventions",
        "DBE NSC 2023 Nov Paper 1 Memo (Gr12, off-grade grounding)",
    ),
    (
        "isizulu_hl_2023_nov_paper2.pdf",
        "isiZulu Home Language",
        10,
        "Reading and Viewing: Literature (Poetry and Drama)",
        "DBE NSC 2023 Nov Paper 2 (Gr12, off-grade grounding)",
    ),
    (
        "isizulu_hl_2023_nov_paper2_memo.pdf",
        "isiZulu Home Language",
        10,
        "Reading and Viewing: Literature (Poetry and Drama)",
        "DBE NSC 2023 Nov Paper 2 Memo (Gr12, off-grade grounding)",
    ),
    (
        "isizulu_hl_2023_nov_paper3.pdf",
        "isiZulu Home Language",
        10,
        "Writing and Presenting",
        "DBE NSC 2023 Nov Paper 3 (Gr12, off-grade grounding)",
    ),
    (
        "isizulu_hl_2023_nov_paper3_memo.pdf",
        "isiZulu Home Language",
        10,
        "Writing and Presenting",
        "DBE NSC 2023 Nov Paper 3 Memo (Gr12, off-grade grounding)",
    ),
]


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """
    Simple fixed-window chunking with overlap, splitting on paragraph
    boundaries where possible rather than mid-sentence. Deliberately not
    a smarter sentence-aware/tokenizer-based splitter -- at this content
    volume (a handful of papers), simple is enough, and simple is easier
    to verify by eye than to trust blindly. Revisit if/when chunk
    quality turns out to matter more than this (see ADR-021 Open items).
    """
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[str] = []
    current = ""
    for para in paragraphs:
        if len(current) + len(para) + 1 <= chunk_size:
            current = f"{current}\n{para}".strip()
            continue
        if current:
            chunks.append(current)
        if len(para) <= chunk_size:
            current = para
        else:
            # a single paragraph longer than chunk_size -- hard-split it
            # with overlap rather than dropping anything.
            step = max(chunk_size - overlap, 1)
            for i in range(0, len(para), step):
                chunks.append(para[i : i + chunk_size])
            current = ""
    if current:
        chunks.append(current)
    return chunks


def extract_pdf_text(path: Path) -> str:
    reader = PdfReader(str(path))
    return "\n\n".join(page.extract_text() or "" for page in reader.pages)


async def _get_topic(session, subject_name: str, grade: int, topic_name: str) -> Topic | None:
    stmt = (
        select(Topic)
        .join(Subject, Topic.subject_id == Subject.id)
        .where(Subject.name == subject_name, Subject.grade == grade, Topic.name == topic_name)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def _ensure_chunk(session, topic_id, source: str, text: str, embedding: list[float]) -> bool:
    existing = await session.execute(
        select(ContentChunk).where(ContentChunk.topic_id == topic_id, ContentChunk.source == source)
    )
    if existing.scalar_one_or_none() is not None:
        return False
    session.add(ContentChunk(topic_id=topic_id, source=source, text=text, embedding=embedding))
    await session.flush()
    return True


async def ingest_file(
    session, relative_path: str, subject_name: str, grade: int, topic_name: str, source_label: str
) -> tuple[int, int]:
    """Returns (chunks_found, chunks_newly_created)."""
    path = CONTENT_SOURCES_DIR / relative_path
    if not path.exists():
        print(f"  SKIP (file not found): {path}")
        return 0, 0

    topic = await _get_topic(session, subject_name, grade, topic_name)
    if topic is None:
        print(
            f"  SKIP (topic not seeded yet): {subject_name} Gr{grade} / {topic_name!r} "
            f"-- run scripts.seed_dev_data first"
        )
        return 0, 0

    text = extract_pdf_text(path) if path.suffix.lower() == ".pdf" else path.read_text(encoding="utf-8")
    chunks = chunk_text(text)
    if not chunks:
        print(f"  SKIP (no extractable text): {path}")
        return 0, 0

    created = 0
    for batch_start in range(0, len(chunks), EMBED_BATCH_SIZE):
        batch = chunks[batch_start : batch_start + EMBED_BATCH_SIZE]
        embeddings = await embed_texts(batch)
        for offset, (chunk_body, embedding) in enumerate(zip(batch, embeddings)):
            index = batch_start + offset
            source = f"{source_label} #{index}"
            if await _ensure_chunk(session, topic.id, source, chunk_body, embedding):
                created += 1
    return len(chunks), created


async def main() -> None:
    async with async_session_factory() as session:
        total_chunks = 0
        total_created = 0
        for relative_path, subject_name, grade, topic_name, source_label in MANIFEST:
            print(f"Ingesting {relative_path} -> {subject_name} Gr{grade} / {topic_name}")
            found, created = await ingest_file(
                session, relative_path, subject_name, grade, topic_name, source_label
            )
            total_chunks += found
            total_created += created
        await session.commit()
        print(
            f"\nDone. {total_chunks} chunks processed, {total_created} new rows written "
            f"(re-running is safe -- already-ingested chunks are skipped)."
        )


if __name__ == "__main__":
    asyncio.run(main())
