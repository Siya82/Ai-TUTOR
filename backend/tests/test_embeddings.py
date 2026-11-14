"""
Unit tests for app.services.embeddings -- only the parts testable
without a real network call. The actual OpenAI HTTP round-trip is
exercised by hand against the real API once OPENAI_API_KEY is set
(see scripts/ingest_content.py's own run instructions), same posture
as TutorClient.ask() (test_tutor_client.py) not mocking the Anthropic
SDK either.
"""

import pytest

from app.services.embeddings import EMBEDDING_DIMENSIONS, EmbeddingsNotConfiguredError, embed_texts


@pytest.mark.asyncio
async def test_raises_clear_error_when_key_missing(monkeypatch):
    from app.core import config

    monkeypatch.setattr(config.settings, "openai_api_key", None)
    with pytest.raises(EmbeddingsNotConfiguredError):
        await embed_texts(["hello"])


def test_embedding_dimensions_matches_schema_vector_size():
    """Regression guard: content_chunks.embedding is Vector(1536)
    (app/models/__init__.py) -- if this constant and that column type
    ever disagree, every write through scripts/ingest_content.py fails
    at the DB layer with a confusing dimension-mismatch error instead
    of here."""
    assert EMBEDDING_DIMENSIONS == 1536
