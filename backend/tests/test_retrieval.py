"""
Unit tests for app.services.retrieval's pure helpers (_cosine_distance,
_format_grounding_text). Pure -- no DB, no network. get_grounding_text
itself needs a DB session + the embeddings API and is exercised by hand
against a real Postgres (not unit-tested here), same posture as every
other DB-touching function in this project (see test_tutor_orchestration.py
for the precedent of unit-testing only the pure pieces).
"""

from types import SimpleNamespace

from app.services.retrieval import PLACEHOLDER_SOURCE_PREFIX, _cosine_distance, _format_grounding_text


def test_cosine_distance_identical_vectors_is_zero():
    v = [1.0, 2.0, 3.0]
    assert _cosine_distance(v, v) == 0.0


def test_cosine_distance_opposite_vectors_is_two():
    a = [1.0, 0.0]
    b = [-1.0, 0.0]
    assert abs(_cosine_distance(a, b) - 2.0) < 1e-9


def test_cosine_distance_orthogonal_vectors_is_one():
    a = [1.0, 0.0]
    b = [0.0, 1.0]
    assert abs(_cosine_distance(a, b) - 1.0) < 1e-9


def test_cosine_distance_zero_vector_is_maximally_dissimilar_not_an_error():
    """A placeholder chunk's embedding is a zero vector -- this must not
    raise ZeroDivisionError, and must never look "close" to a real
    query embedding."""
    zero = [0.0, 0.0, 0.0]
    real = [1.0, 2.0, 3.0]
    assert _cosine_distance(zero, real) == 1.0
    assert _cosine_distance(real, zero) == 1.0
    assert _cosine_distance(zero, zero) == 1.0


def test_placeholder_source_prefix_matches_seed_dev_data():
    """Regression guard: this prefix must keep matching the literal
    source string seed_dev_data.py's ensure_placeholder_content_chunk()
    writes, or placeholder chunks silently stop being excluded from
    grounding retrieval."""
    seed_source = "placeholder (RAG ingestion not yet built, see REBUILD_SPEC.md Section 8)"
    assert seed_source.startswith(PLACEHOLDER_SOURCE_PREFIX)


def _chunk(source: str, text: str):
    return SimpleNamespace(source=source, text=text)


def test_format_grounding_text_includes_all_chunk_bodies():
    chunks = [_chunk("Paper 1 #0", "umfundi means student"), _chunk("Paper 1 #1", "izincwadi means books")]
    formatted = _format_grounding_text(chunks)
    assert "umfundi means student" in formatted
    assert "izincwadi means books" in formatted


def test_format_grounding_text_lists_sources_once_each():
    chunks = [_chunk("Paper 1 #0", "a"), _chunk("Paper 1 #1", "b"), _chunk("Paper 2 #0", "c")]
    formatted = _format_grounding_text(chunks)
    assert formatted.count("Paper 1 #0") == 1
    assert "Paper 2 #0" in formatted


def test_format_grounding_text_instructs_preference_over_general_knowledge():
    chunks = [_chunk("Paper 1 #0", "some isiZulu text")]
    formatted = _format_grounding_text(chunks)
    assert "ADR-021" in formatted
    assert "Prefer this material" in formatted
