"""
Tests for the e-book library (ADR-032): app/services/books.py's pure helpers
and scripts/ingest_books.py's manifest checks. No DB, no network.
"""

import io
import uuid
from types import SimpleNamespace

import pytest
from pypdf import PdfReader, PdfWriter

from app.services.books import (
    MAX_PAGE_CHARS,
    MAX_SELECTION_CHARS,
    book_history_summary,
    build_book_passage,
    single_page_pdf,
    topic_for_page,
)
from scripts.ingest_books import BOOKS, first_line, page_source_label, validate_ranges


def _range(start, end):
    return SimpleNamespace(topic_id=uuid.uuid4(), start_page=start, end_page=end)


def test_topic_for_page_finds_containing_range():
    a, b = _range(10, 30), _range(31, 60)
    assert topic_for_page([b, a], 10) is a
    assert topic_for_page([b, a], 31) is b
    assert topic_for_page([b, a], 61) is None
    assert topic_for_page([], 5) is None


def test_passage_includes_page_selection_and_attribution():
    text = build_book_passage(
        title="Everything Maths Grade 10",
        page_number=87,
        page_text="Solve 2x + 3 = 7.",
        selected_text="  2x + 3 = 7 ",
        attribution="Siyavula, CC BY 3.0",
    )
    assert "Everything Maths Grade 10" in text and "page 87" in text and "p. 87" in text
    assert "Solve 2x + 3 = 7." in text
    assert 'highlighted: "2x + 3 = 7"' in text
    assert "CC BY 3.0" in text


def test_passage_caps_long_page_and_selection_and_handles_empty_page():
    long = build_book_passage(
        title="T", page_number=1, page_text="x" * (MAX_PAGE_CHARS + 500),
        selected_text="y" * (MAX_SELECTION_CHARS + 500), attribution="A",
    )
    assert "x" * (MAX_PAGE_CHARS + 1) not in long
    assert "y" * (MAX_SELECTION_CHARS + 1) not in long
    empty = build_book_passage(title="T", page_number=2, page_text="", selected_text=None, attribution="A")
    assert "no extractable text" in empty
    assert "highlighted" not in empty


def test_history_summary_is_short():
    s = book_history_summary("Everything Maths Grade 10", 87, "a " * 200)
    assert s.startswith("(Reading Everything Maths Grade 10, p. 87")
    assert len(s) < 160
    assert book_history_summary("T", 3, None) == "(Reading T, p. 3)"


def _pdf(pages: int) -> bytes:
    w = PdfWriter()
    for _ in range(pages):
        w.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    w.write(buf)
    return buf.getvalue()


def test_single_page_pdf(tmp_path):
    path = tmp_path / "book.pdf"
    path.write_bytes(_pdf(5))
    one = PdfReader(io.BytesIO(single_page_pdf(path, 3)))
    assert len(one.pages) == 1
    with pytest.raises(IndexError):
        single_page_pdf(path, 6)
    with pytest.raises(IndexError):
        single_page_pdf(path, 0)


def test_validate_ranges():
    assert validate_ranges({"Exponents": [10, 20]}, 100) == []
    assert validate_ranges({"Exponents": [20, 10]}, 100)
    assert validate_ranges({"Exponents": [0, 10]}, 100)
    assert "PDF has 50 pages" in validate_ranges({"Exponents": [10, 60]}, 50)[0]
    assert validate_ranges({"Exponents": "10-20"}, 100)


def test_page_source_label():
    assert page_source_label("Everything Maths Grade 10", "Siyavula", 87, 0, 1) == "Everything Maths Grade 10 (Siyavula), p. 87"
    assert page_source_label("T", None, 4, 1, 3) == "T, p. 4 #2"


def test_first_line():
    assert first_line("\n\n  Chapter 3: Exponents \nmore") == "Chapter 3: Exponents"
    assert first_line("") == "(no text on this page)"


def test_manifest_is_cc_by_siyavula_only():
    # ADR-032: only CC-BY (commercial use allowed) books, never "Mind the Gap" (non-commercial)
    for spec in BOOKS:
        assert spec["licence"] == "CC-BY 3.0"
        assert "CC BY 3.0" in spec["attribution"]
        assert "mind" not in spec["file_name"].lower()
