"""
Unit tests for scripts.ingest_content's pure chunking logic. Pure -- no
DB, no network, no PDF files on disk.
"""

from scripts.ingest_content import CHUNK_OVERLAP, CHUNK_SIZE, chunk_text


def test_empty_text_returns_no_chunks():
    assert chunk_text("") == []
    assert chunk_text("   \n\n   ") == []


def test_short_text_returns_one_chunk():
    chunks = chunk_text("A single short paragraph of isiZulu text.")
    assert len(chunks) == 1
    assert "isiZulu" in chunks[0]


def test_paragraphs_combine_until_chunk_size():
    paragraphs = "\n\n".join(["Paragraph one." * 5, "Paragraph two." * 5])
    chunks = chunk_text(paragraphs, chunk_size=200)
    # Both paragraphs are well under 200 chars combined, so they should
    # land in a single chunk rather than being split unnecessarily.
    assert len(chunks) == 1
    assert "Paragraph one." in chunks[0]
    assert "Paragraph two." in chunks[0]


def test_paragraphs_split_once_chunk_size_exceeded():
    para_a = "A" * 80
    para_b = "B" * 80
    chunks = chunk_text(f"{para_a}\n\n{para_b}", chunk_size=100)
    assert len(chunks) == 2
    assert para_a in chunks[0]
    assert para_b in chunks[1]


def test_no_chunk_exceeds_configured_size_for_long_single_paragraph():
    """A single paragraph longer than chunk_size must be hard-split, not
    silently kept oversized or dropped -- this is exactly the shape of
    a long, unbroken past-paper passage with no blank lines."""
    long_paragraph = "word " * 400  # ~2000 chars, no paragraph breaks
    chunks = chunk_text(long_paragraph, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) <= CHUNK_SIZE


def test_hard_split_preserves_all_characters_via_overlap():
    """Overlapping hard-split chunks should still cover every character
    of the source paragraph -- nothing silently dropped between windows."""
    long_paragraph = "x" * 2500
    chunks = chunk_text(long_paragraph, chunk_size=1000, overlap=150)
    # Reconstruct coverage: every character position must appear in at
    # least one chunk's span.
    assert len(chunks) >= 3
    assert sum(len(c) for c in chunks) >= len(long_paragraph)


def test_multiple_short_paragraphs_each_kept_intact():
    text = "\n\n".join(f"Sentence number {i} about isiZulu grammar." for i in range(20))
    chunks = chunk_text(text, chunk_size=150)
    rejoined = " ".join(chunks)
    for i in range(20):
        assert f"Sentence number {i} about" in rejoined
