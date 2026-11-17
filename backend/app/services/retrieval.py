"""
RAG grounding retrieval (ADR-021): given a topic and the learner's
message, finds the most relevant ingested ContentChunk rows (if any
real ones have been written by scripts/ingest_content.py) and returns
them as a single grounding text block for the tutor system prompt
(see app/services/tutor.py's grounding_text parameter).

Returns None whenever a topic has no real (non-placeholder) chunks yet
-- which is every topic except the ones scripts/ingest_content.py has
actually been run against (isiZulu/English Home Language, as of
ADR-021). Callers MUST treat None as "fall back to the existing
REBUILD_SPEC.md Section 8 placeholder text", not as an error.

Ranking is done in plain Python (load the topic's real chunks, sort by
cosine distance to the query embedding) rather than a pgvector ORDER BY
in SQL. At the content volume this project has today (a handful of
chunks per topic from a couple of past papers) that's simpler to read
and to unit-test than wiring up pgvector's SQLAlchemy distance
operators, at the cost of not scaling past a small number of chunks
per topic. Revisit with a real ORDER BY ... <-> ... query once a topic
has enough ingested content for that cost to matter -- see Open items
in docs/ADR-021-rag-content-ingestion.md.
"""

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ContentChunk
from app.services.embeddings import EmbeddingsNotConfiguredError, embed_text

# Must match seed_dev_data.py's ensure_placeholder_content_chunk() source
# string exactly (its leading words, not the whole string -- the full
# string also carries a parenthetical that doesn't matter here). Chunks
# with a source starting with this prefix are the zero-vector
# placeholders -- never real grounding, always excluded.
PLACEHOLDER_SOURCE_PREFIX = "placeholder ("

GROUNDING_CHUNK_LIMIT = 4


def _cosine_distance(a: list[float], b: list[float]) -> float:
    """0.0 = identical direction, 1.0 = orthogonal, 2.0 = opposite. A zero
    vector (e.g. an accidentally-unfiltered placeholder) has no defined
    direction, so it's scored as maximally dissimilar (1.0) rather than
    raising a divide-by-zero."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 1.0
    return 1.0 - (dot / (norm_a * norm_b))


def _format_grounding_text(chunks: list[ContentChunk]) -> str:
    # UPDATED 17 Nov 2026 (ADR-032): each chunk carries its own source label
    # (e.g. "Everything Maths Grade 10 (Siyavula), p. 87") so the tutor can
    # point the learner to the exact page. The header no longer repeats the
    # source list, since every excerpt is now labelled where it appears.
    body = "\n\n---\n\n".join(f"[{c.source}]\n{c.text}" for c in chunks)
    return (
        f"[CAPS content grounding -- real ingested source material, each excerpt labelled with its source, "
        f"see ADR-021. Prefer this material over your own general knowledge whenever it's "
        f"relevant, especially for matching/identification/fact-based questions -- that is "
        f"exactly the failure mode this was built to reduce. If this material doesn't cover "
        f"what the learner is asking, fall back to general CAPS curriculum knowledge rather "
        f"than forcing a match to it. When an excerpt below is labelled with a book page, "
        f"tell the learner where to read more, e.g. 'see p. 87 of Everything Maths Grade 10'.]"
        f"\n\n{body}"
    )


async def get_grounding_text(
    session: AsyncSession, topic_id, query_text: str
) -> str | None:
    """
    `query_text` is usually the learner's current message; routers/tutor.py
    falls back to the topic name when the learner's turn has no text of
    its own (an attachment-only turn).

    Embedding/network failures (missing OPENAI_API_KEY, OpenAI being
    down, a timeout) are swallowed here and treated the same as "no
    grounding available" -- a single tutor turn should never fail just
    because the grounding lookup had a bad moment. This is a deliberate
    availability-over-grounding tradeoff; see Open items in
    docs/ADR-021-rag-content-ingestion.md.
    """
    result = await session.execute(
        select(ContentChunk)
        .where(ContentChunk.topic_id == topic_id)
        .where(~ContentChunk.source.startswith(PLACEHOLDER_SOURCE_PREFIX))
    )
    real_chunks = result.scalars().all()
    if not real_chunks:
        return None

    try:
        query_vector = await embed_text(query_text)
    except (EmbeddingsNotConfiguredError, httpx.HTTPError):
        return None

    ranked = sorted(real_chunks, key=lambda c: _cosine_distance(c.embedding, query_vector))
    return _format_grounding_text(ranked[:GROUNDING_CHUNK_LIMIT])
