"""
POST /attachments -- a student uploads a photo, PDF, or Word document
to go with a tutor message. See docs/ADR-016-student-file-attachments.md.

Upload happens BEFORE the student's message is sent (the composer shows
a preview/confirmation first) -- so this endpoint only creates the
Attachment row and returns its id; POST /tutor/message (app/routers/
tutor.py) is what actually reads the file, builds the Claude content
blocks, and backfills session_id/message_id onto this row once a real
TutorMessage exists for it.

No authentication yet (step 8, not done) -- consistent with every other
endpoint in this API today.
"""

import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models import Attachment, Learner
from app.schemas.attachments import AttachmentUploadResponse
from app.services.attachments import (
    MAX_UPLOAD_BYTES,
    classify_content_type,
    extract_docx_text,
    extract_pdf_text,
    save_upload,
)

router = APIRouter(prefix="/attachments", tags=["attachments"])


@router.post("/", response_model=AttachmentUploadResponse)
async def upload_attachment(
    learner_id: uuid.UUID = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> Attachment:
    learner = await db.get(Learner, learner_id)
    if learner is None:
        raise HTTPException(status_code=404, detail="Learner not found")

    content_type = file.content_type or "application/octet-stream"
    kind = classify_content_type(content_type, file.filename or "upload")
    if kind is None:
        raise HTTPException(
            status_code=415,
            detail=(
                "Unsupported file type. THUTOra currently accepts images "
                "(PNG/JPEG/WEBP/GIF), PDF, and Word (.docx) files."
            ),
        )

    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large (max {MAX_UPLOAD_BYTES // (1024 * 1024)}MB).",
        )

    storage_path = save_upload(data, file.filename or "upload", settings.upload_dir)

    extracted_text: str | None = None
    extraction_warning: str | None = None
    if kind == "pdf":
        extracted_text, extraction_warning = extract_pdf_text(storage_path)
    elif kind == "docx":
        extracted_text, extraction_warning = extract_docx_text(storage_path)
    # "image": no extraction -- sent to Claude as a vision block at
    # message time instead (see app/services/attachments.py).

    attachment = Attachment(
        learner_id=learner.id,
        original_filename=file.filename or "upload",
        content_type=content_type,
        kind=kind,
        storage_path=storage_path,
        extracted_text=extracted_text,
        extraction_warning=extraction_warning,
    )
    db.add(attachment)
    await db.commit()
    await db.refresh(attachment)
    return attachment
