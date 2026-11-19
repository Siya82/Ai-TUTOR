"""
Pydantic schemas for POST /attachments.

NEW 13 Nov 2026 (ADR-016, student file attachments).
FIX 14 Nov 2026 (ADR-017, student login): the endpoint itself no longer
takes learner_id from the request -- it's resolved from the
Authorization bearer token instead (app/core/security.py).
"""

import uuid

from pydantic import BaseModel, ConfigDict


class AttachmentUploadResponse(BaseModel):
    id: uuid.UUID
    kind: str  # "image" | "pdf" | "docx"
    original_filename: str
    # Set only for a PDF/docx that came back with no usable text (e.g. a
    # scanned worksheet with no text layer) -- the frontend shows this to
    # the student directly so they can try a photo instead, rather than
    # silently sending an attachment the tutor can't actually read.
    extraction_warning: str | None = None

    model_config = ConfigDict(from_attributes=True)  # deep scan L5 (Pydantic 2 style)
