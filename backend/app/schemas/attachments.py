"""
Pydantic schemas for POST /attachments.

NEW 13 Nov 2026 (ADR-016, student file attachments). Same posture as
every other endpoint in this API today: no authentication yet (step 8,
not done) -- learner_id in the request is a basic sanity check, not a
real permission boundary.
"""

import uuid

from pydantic import BaseModel


class AttachmentUploadResponse(BaseModel):
    id: uuid.UUID
    kind: str  # "image" | "pdf" | "docx"
    original_filename: str
    # Set only for a PDF/docx that came back with no usable text (e.g. a
    # scanned worksheet with no text layer) -- the frontend shows this to
    # the student directly so they can try a photo instead, rather than
    # silently sending an attachment the tutor can't actually read.
    extraction_warning: str | None = None

    class Config:
        from_attributes = True
