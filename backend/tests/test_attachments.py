"""
Tests for app/services/attachments.py (ADR-016, student file
attachments). Pure -- no DB, no network, no FastAPI app, matching every
other service test in this project (test_math_validator.py,
test_math_guard.py, ...). Fixture PDFs/images are built in-memory with
pypdf/zlib rather than committed as binary test assets.
"""

import struct
import zlib

import pytest
from docx import Document
from pypdf import PdfWriter

from app.services.attachments import (
    build_attachment_content_blocks,
    classify_content_type,
    extract_docx_text,
    extract_pdf_text,
    history_summary_for,
    save_upload,
)


# ---------------------------------------------------------------------------
# classify_content_type
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "content_type,filename,expected",
    [
        ("image/png", "worksheet.png", "image"),
        ("image/jpeg", "photo.jpg", "image"),
        ("image/webp", "photo.webp", "image"),
        ("image/gif", "photo.gif", "image"),
        ("application/pdf", "past_paper.pdf", "pdf"),
        (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "homework.docx",
            "docx",
        ),
    ],
)
def test_classify_content_type_recognizes_each_supported_kind(content_type, filename, expected):
    assert classify_content_type(content_type, filename) == expected


def test_classify_content_type_falls_back_to_extension_for_a_generic_content_type():
    # Some mobile upload UIs send a generic content_type instead of
    # sniffing the real one -- the filename extension is the fallback.
    assert classify_content_type("application/octet-stream", "worksheet.png") == "image"
    assert classify_content_type("application/octet-stream", "past_paper.pdf") == "pdf"
    assert classify_content_type("application/octet-stream", "homework.docx") == "docx"


def test_classify_content_type_returns_none_for_an_unsupported_type():
    assert classify_content_type("application/zip", "archive.zip") is None
    assert classify_content_type("text/plain", "notes") is None


# ---------------------------------------------------------------------------
# save_upload
# ---------------------------------------------------------------------------

def test_save_upload_writes_bytes_under_a_fresh_uuid_subfolder(tmp_path):
    path = save_upload(b"hello world", "worksheet.png", tmp_path)
    assert path.endswith("worksheet.png")
    assert open(path, "rb").read() == b"hello world"
    # Written one level under the upload root, in its own subfolder.
    assert str(tmp_path) in path


def test_save_upload_basenames_a_path_traversal_attempt(tmp_path):
    # original_filename is attacker-controlled input from the HTTP
    # multipart form -- Path(...).name must strip any directory
    # components so it can never escape its own fresh uuid subfolder.
    path = save_upload(b"x", "../../etc/passwd", tmp_path)
    assert path.endswith("/passwd")
    assert ".." not in path
    assert str(tmp_path) in path


def test_save_upload_lets_two_same_named_files_coexist(tmp_path):
    # Two students' "worksheet.pdf" must never collide -- each upload
    # gets its own uuid subfolder.
    path_a = save_upload(b"a", "worksheet.pdf", tmp_path)
    path_b = save_upload(b"b", "worksheet.pdf", tmp_path)
    assert path_a != path_b
    assert open(path_a, "rb").read() == b"a"
    assert open(path_b, "rb").read() == b"b"


# ---------------------------------------------------------------------------
# extract_pdf_text
# ---------------------------------------------------------------------------

def _write_blank_pdf(path):
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    with open(path, "wb") as f:
        writer.write(f)


def _write_text_pdf(path, text):
    # pypdf itself has no simple text-drawing API, so we build a minimal
    # one-page PDF with a content stream by hand, including a real xref
    # table/trailer (pypdf is strict about this, unlike some viewers) --
    # enough for PdfReader.extract_text() to recover the string back out.
    content = f"BT /F1 24 Tf 20 150 Td ({text}) Tj ET".encode("latin-1")
    objects = [
        b"<</Type/Catalog/Pages 2 0 R>>",
        b"<</Type/Pages/Kids[3 0 R]/Count 1>>",
        b"<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]"
        b"/Resources<</Font<</F1 4 0 R>>>>/Contents 5 0 R>>",
        b"<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>",
        b"<</Length " + str(len(content)).encode() + b">>\nstream\n" + content + b"\nendstream",
    ]
    out = b"%PDF-1.4\n"
    offsets = [0]
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref_offset = len(out)
    n = len(objects) + 1
    out += f"xref\n0 {n}\n".encode() + b"0000000000 65535 f \n"
    for off in offsets[1:]:
        out += f"{off:010d} 00000 n \n".encode()
    out += (
        b"trailer\n<</Size " + str(n).encode() + b"/Root 1 0 R>>\n"
        b"startxref\n" + str(xref_offset).encode() + b"\n%%EOF"
    )
    with open(path, "wb") as f:
        f.write(out)


def test_extract_pdf_text_returns_a_warning_for_a_scanned_pdf_with_no_text_layer(tmp_path):
    path = tmp_path / "scanned.pdf"
    _write_blank_pdf(path)
    text, warning = extract_pdf_text(str(path))
    assert text == ""
    assert warning is not None
    assert "scanned" in warning.lower()
    assert "photo" in warning.lower()


def test_extract_pdf_text_returns_the_text_of_a_real_text_pdf(tmp_path):
    path = tmp_path / "typed.pdf"
    _write_text_pdf(path, "Solve for x: 2x + 3 = 11")
    text, warning = extract_pdf_text(str(path))
    assert warning is None
    assert "Solve for x" in text


def test_extract_pdf_text_returns_a_warning_for_an_unreadable_file(tmp_path):
    path = tmp_path / "not_a_pdf.pdf"
    path.write_bytes(b"this is not a pdf at all")
    text, warning = extract_pdf_text(str(path))
    assert text == ""
    assert warning is not None


# ---------------------------------------------------------------------------
# extract_docx_text
# ---------------------------------------------------------------------------

def test_extract_docx_text_returns_the_paragraphs_of_a_real_docx(tmp_path):
    path = tmp_path / "homework.docx"
    doc = Document()
    doc.add_paragraph("Question 3: factorise x^2 - 5x + 6.")
    doc.add_paragraph("My attempt: (x - 2)(x - 3)")
    doc.save(str(path))

    text, warning = extract_docx_text(str(path))
    assert warning is None
    assert "factorise" in text
    assert "(x - 2)(x - 3)" in text


def test_extract_docx_text_returns_a_warning_for_an_empty_document(tmp_path):
    path = tmp_path / "empty.docx"
    Document().save(str(path))
    text, warning = extract_docx_text(str(path))
    assert text == ""
    assert warning is not None


def test_extract_docx_text_returns_a_warning_for_an_unreadable_file(tmp_path):
    path = tmp_path / "not_a_docx.docx"
    path.write_bytes(b"this is not a docx at all")
    text, warning = extract_docx_text(str(path))
    assert text == ""
    assert warning is not None


# ---------------------------------------------------------------------------
# build_attachment_content_blocks
# ---------------------------------------------------------------------------

def _write_minimal_png(path):
    # A hand-built 1x1 transparent PNG -- small enough to inline here
    # rather than committing a binary fixture file.
    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(
            ">I", zlib.crc32(tag + data) & 0xFFFFFFFF
        )

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0))
    raw = b"\x00\x00\x00\x00\x00"  # filter byte + 1 RGBA pixel
    idat = chunk(b"IDAT", zlib.compress(raw))
    iend = chunk(b"IEND", b"")
    path.write_bytes(sig + ihdr + idat + iend)


def test_build_attachment_content_blocks_for_an_image_produces_a_vision_block(tmp_path):
    png_path = tmp_path / "worksheet.png"
    _write_minimal_png(png_path)

    blocks = build_attachment_content_blocks(
        [
            {
                "kind": "image",
                "storage_path": str(png_path),
                "original_filename": "worksheet.png",
                "extracted_text": None,
                "extraction_warning": None,
            }
        ]
    )

    assert len(blocks) == 2
    assert blocks[0]["type"] == "image"
    assert blocks[0]["source"]["media_type"] == "image/png"
    assert blocks[0]["source"]["type"] == "base64"
    assert blocks[1]["type"] == "text"
    assert "worksheet.png" in blocks[1]["text"]


def test_build_attachment_content_blocks_for_a_pdf_with_text_includes_the_extracted_text():
    blocks = build_attachment_content_blocks(
        [
            {
                "kind": "pdf",
                "storage_path": "irrelevant.pdf",
                "original_filename": "past_paper.pdf",
                "extracted_text": "Question 1: ...",
                "extraction_warning": None,
            }
        ]
    )
    assert len(blocks) == 1
    assert blocks[0]["type"] == "text"
    assert "past_paper.pdf" in blocks[0]["text"]
    assert "Question 1: ..." in blocks[0]["text"]


def test_build_attachment_content_blocks_for_a_pdf_with_a_warning_includes_the_warning_not_the_text():
    blocks = build_attachment_content_blocks(
        [
            {
                "kind": "pdf",
                "storage_path": "irrelevant.pdf",
                "original_filename": "scan.pdf",
                "extracted_text": None,
                "extraction_warning": "This PDF has no extractable text (likely a scanned worksheet).",
            }
        ]
    )
    assert len(blocks) == 1
    assert "scan.pdf" in blocks[0]["text"]
    assert "scanned worksheet" in blocks[0]["text"]


def test_build_attachment_content_blocks_preserves_order_across_multiple_attachments(tmp_path):
    png_path = tmp_path / "a.png"
    _write_minimal_png(png_path)

    blocks = build_attachment_content_blocks(
        [
            {
                "kind": "image",
                "storage_path": str(png_path),
                "original_filename": "a.png",
                "extracted_text": None,
                "extraction_warning": None,
            },
            {
                "kind": "docx",
                "storage_path": "irrelevant.docx",
                "original_filename": "b.docx",
                "extracted_text": "some text",
                "extraction_warning": None,
            },
        ]
    )
    # image -> [image block, text block]; docx -> [text block]
    assert len(blocks) == 3
    assert blocks[0]["type"] == "image"
    assert "a.png" in blocks[1]["text"]
    assert "b.docx" in blocks[2]["text"]


# ---------------------------------------------------------------------------
# history_summary_for
# ---------------------------------------------------------------------------

def test_history_summary_for_with_no_attachments_returns_the_message_unchanged():
    assert history_summary_for([], "How do I solve this?") == "How do I solve this?"


def test_history_summary_for_with_attachments_prefixes_the_filenames():
    attachments = [
        {"original_filename": "worksheet_photo.png"},
        {"original_filename": "scan.pdf"},
    ]
    result = history_summary_for(attachments, "How do I solve this?")
    assert result == "[Attached: worksheet_photo.png, scan.pdf]\nHow do I solve this?"
