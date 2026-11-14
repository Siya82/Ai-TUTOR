"""
Minimal OpenAI embeddings client, added for real RAG content grounding
(ADR-021) -- the first actual implementation of what
scripts/seed_dev_data.py's PLACEHOLDER_EMBEDDING and
ensure_placeholder_content_chunk() have stood in for since the schema
was first built.

Uses plain httpx (already a dependency, see requirements.txt) rather
than adding the full `openai` SDK for what is, so far, a single
endpoint. Separate from ANTHROPIC_API_KEY/TutorClient (tutor.py) on
purpose: Claude itself does not expose an embeddings endpoint.

1536 was already content_chunks.embedding's pgvector dimension before
this file existed (see app/models/__init__.py) -- that is exactly
OpenAI's text-embedding-3-small (and legacy ada-002) output size, which
is almost certainly why 1536 was chosen in the first place. This reuses
the provider the schema already implied rather than introducing an
arbitrary new one. See docs/ADR-021-rag-content-ingestion.md.

Requires OPENAI_API_KEY in backend/.env (see app/core/config.py) -- add
it yourself; this project's standing rule is that Claude never reads or
writes .env contents.
"""

import httpx

from app.core.config import settings

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536  # must match content_chunks.embedding's Vector(1536)

_API_URL = "https://api.openai.com/v1/embeddings"
_REQUEST_TIMEOUT_SECONDS = 30.0


class EmbeddingsNotConfiguredError(RuntimeError):
    """Raised when OPENAI_API_KEY is missing -- a clear, fail-fast error
    instead of a confusing httpx 401 three frames away from the real
    cause."""


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """
    Embeds a batch of strings in one API call. Order of the returned
    list matches `texts` -- OpenAI's response is expected to preserve
    input order already, but each item also carries its own `index`, so
    this sorts by that defensively rather than assuming order holds.

    Raises EmbeddingsNotConfiguredError if OPENAI_API_KEY isn't set, and
    lets httpx.HTTPStatusError/HTTPError propagate on a real API failure
    -- callers that need ingestion/a tutor turn to survive a transient
    embeddings-provider failure (see app/services/retrieval.py) are
    responsible for catching those, not this function.
    """
    if not settings.openai_api_key:
        raise EmbeddingsNotConfiguredError(
            "OPENAI_API_KEY is not set in backend/.env -- required for RAG content "
            "ingestion/retrieval (ADR-021). Add it yourself; this project's standing "
            "rule is that Claude never reads or writes .env contents."
        )
    async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT_SECONDS) as client:
        response = await client.post(
            _API_URL,
            headers={"Authorization": f"Bearer {settings.openai_api_key}"},
            json={"model": EMBEDDING_MODEL, "input": texts},
        )
        response.raise_for_status()
        data = response.json()
    ordered = sorted(data["data"], key=lambda item: item["index"])
    return [item["embedding"] for item in ordered]


async def embed_text(text: str) -> list[float]:
    """Convenience wrapper for the common single-text case (e.g. embedding
    a learner's question at retrieval time in app/services/retrieval.py)."""
    return (await embed_texts([text]))[0]
