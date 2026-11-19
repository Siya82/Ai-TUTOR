"""
File-attachment support for THUTOra's chat: lets a student attach or
paste a photo of a worksheet, a PDF, or a Word document alongside their
question. See docs/ADR-016-student-file-attachments.md.

Three supported kinds:
- "image" (png/jpg/jpeg/webp/gif): sent directly to Claude as a vision
  content block -- no server-side extraction, since a photographed
  worksheet (handwriting, diagrams, layout) loses real information to
  OCR that Claude's own vision can read directly.
- "pdf": text extracted server-side via pypdf. A scanned/image-only PDF
  with no text layer yields an honest extraction_warning rather than
  silently sending nothing -- same "honest limitation" discipline as
  MathGuard's own documented gaps (see REBUILD_SPEC.md Section 1).
- "docx": text extracted server-side via python-docx.

Deliberately DB- and request-free: every function here takes plain
bytes/paths/dicts in and returns plain data out, so this module is
pytest'd without a database or the FastAPI app, matching every other
service module in this project (math_validator.py, diagnosis.py, ...).
"""

import base64
import uuid
from pathlib import Path

from docx import Document
from pypdf import PdfReader

IMAGE_CONTENT_TYPES = {
    "image/png": "png",
    "image/jpeg": "jpeg",
    "image/jpg": "jpeg",
    "image/webp": "webp",
    "image/gif": "gif",
}
PDF_CONTENT_TYPES = {"application/pdf"}
DOCX_CONTENT_TYPES = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

_IMAGE_EXTENSIONS = {".png": "png", ".jpg": "jpeg", ".jpeg": "jpeg", ".webp": "webp", ".gif": "gif"}

MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 20MB -- generous for a worksheet PDF

# NEW 17 Nov 2026 (code review #3): Claude refuses images over 5MB, which
# used to surface as a tutor 500. The browser now shrinks photos before
# upload (frontend/src/utils/shrinkImage.js); this is the server-side floor
# for anything that still arrives too big.
MAX_IMAGE_BYTES = 5 * 1024 * 1024

# Below this many characters of extracted text, treat a PDF/docx as having
# "no usable text" rather than silently sending a near-empty block to
# Claude -- a scanned worksheet saved as a PDF is a real, common case.
MIN_EXTRACTED_TEXT_CHARS = 20


def classify_content_type(content_type: str, filename: str) -> str | None:
    """
    Returns "image" | "pdf" | "docx", or None if unsupported. Falls back
    to the filename extension when the browser-supplied content_type is
    generic (e.g. "application/octet-stream", seen from some mobile
    upload UIs that don't sniff the real type).
    """
    if content_type in IMAGE_CONTENT_TYPES:
        return "image"
    if content_type in PDF_CONTENT_TYPES:
        return "pdf"
    if content_type in DOCX_CONTENT_TYPES:
        return "docx"
    ext = Path(filename).suffix.lower()
    if ext in _IMAGE_EXTENSIONS:
        return "image"
    if ext == ".pdf":
        return "pdf"
    if ext == ".docx":
        return "docx"
    return None


def save_upload(data: bytes, original_filename: str, upload_root: str | Path) -> str:
    """
    Writes the uploaded bytes to a new uuid-named subfolder under
    upload_root (so two students' same-named "worksheet.pdf" never
    collide), and returns the storage path as a string. The original
    filename is kept only for its basename -- Path(...).name strips any
    directory components the browser might have sent -- so it can never
    be used to write outside its own fresh subfolder.
    """
    safe_name = Path(original_filename).name or "upload"
    folder = Path(upload_root) / str(uuid.uuid4())
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / safe_name
    path.write_bytes(data)
    return str(path)


# deep scan M4: never trust the browser's content type -- check what the
# file actually is from its first bytes.
_SIGNATURES = {
    "pdf": (b"%PDF-",),
    "docx": (b"PK\x03\x04",),
    "image": (b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff", b"GIF87a", b"GIF89a"),
}
MAX_PDF_PAGES = 40


def content_matches_kind(data: bytes, kind: str) -> bool:
    """True when the file's own bytes say it is `kind` (WEBP: RIFF....WEBP)."""
    if kind == "image" and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return True
    return any(data.startswith(sig) for sig in _SIGNATURES.get(kind, ()))


def extract_pdf_text(path: str) -> tuple[str, str | None]:
    """
    Returns (extracted_text, warning). warning is set (text is "") when
    the PDF has no meaningful extractable text -- most often a scanned
    worksheet with no text layer, a real and expected case for CAPS past
    papers, not a bug to silently paper over (ADR-016).
    """
    try:
        reader = PdfReader(path)
        # deep scan M4: a worksheet never needs more than this many pages, and
        # a hostile PDF with thousands of pages shouldn't tie the server up
        pages_text = [page.extract_text() or "" for page in list(reader.pages)[:MAX_PDF_PAGES]]
    except Exception as exc:
        return "", (
            f"Could not read this PDF ({exc.__class__.__name__}). Try attaching "
            f"a photo of each page instead."
        )
    text = "\n\n".join(t.strip() for t in pages_text if t.strip())
    if len(text) < MIN_EXTRACTED_TEXT_CHARS:
        return "", (
            "This PDF has no extractable text (likely a scanned worksheet) -- "
            "THUTOra can't read it this way yet. Try attaching a photo of each "
            "page instead, which THUTOra can read directly."
        )
    return text, None


def extract_docx_text(path: str) -> tuple[str, str | None]:
    """Returns (extracted_text, warning), same shape as extract_pdf_text."""
    try:
        doc = Document(path)
        text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    except Exception as exc:
        return "", f"Could not read this Word document ({exc.__class__.__name__})."
    if len(text.strip()) < MIN_EXTRACTED_TEXT_CHARS:
        return "", "This Word document appears to be empty or has no readable text."
    return text, None


def _image_media_type(storage_path: str) -> str:
    ext = Path(storage_path).suffix.lower()
    kind = _IMAGE_EXTENSIONS.get(ext, "png")
    return f"image/{kind}"


def build_attachment_content_blocks(attachments: list[dict]) -> list[dict]:
    """
    Builds the Claude-API content blocks for a list of attachment
    records, in order, to prepend to the student's own text block for
    that turn.

    Each attachment dict: {"kind", "storage_path", "original_filename",
    "extracted_text", "extraction_warning"}. Pure aside from reading the
    image bytes it's told to read -- no DB, no request object -- so
    it's testable with plain dicts and a real temp file on disk.
    """
    blocks: list[dict] = []
    for att in attachments:
        if att["kind"] == "image":
            media_type = _image_media_type(att["storage_path"])
            with open(att["storage_path"], "rb") as f:
                data = base64.b64encode(f.read()).decode("ascii")
            blocks.append({
                "type": "image",
                "source": {"type": "base64", "media_type": media_type, "data": data},
            })
            blocks.append({
                "type": "text",
                "text": f"[Student attached an image: {att['original_filename']}]",
            })
        else:  # "pdf" / "docx"
            label = att["kind"].upper()
            if att.get("extraction_warning"):
                text = (
                    f"[Student attached a {label} ({att['original_filename']}) -- "
                    f"{att['extraction_warning']}]"
                )
            else:
                text = (
                    f"[Student attached a {label} ({att['original_filename']}), "
                    f"extracted text below:]\n{att['extracted_text']}"
                )
            blocks.append({"type": "text", "text": text})
    return blocks


def history_summary_for(attachments: list[dict], message_text: str) -> str:
    """
    Builds the plain-text version of a student's turn that actually gets
    PERSISTED as TutorMessage.content -- a readable summary, not the
    rich multimodal block list, so later turns' history replay to Claude
    stays simple text and doesn't re-spend tokens resending an image
    that was already answered (ADR-016, "Wiring into the tutor turn").
    """
    if not attachments:
        return message_text
    names = ", ".join(a["original_filename"] for a in attachments)
    return f"[Attached: {names}]\n{message_text}"
