"""
POST /attachments -- a student uploads a photo, PDF, or Word document
to go with a tutor message. See docs/ADR-016-student-file-attachments.md.

Upload happens BEFORE the student's message is sent (the composer shows
a preview/confirmation first) -- so this endpoint only creates the
Attachment row and returns its id; POST /tutor/message (app/routers/
tutor.py) is what actually reads the file, builds the Claude content
blocks, and backfills session_id/message_id onto this row once a real
TutorMessage exists for it.

FIX 14 Nov 2026 (ADR-017, student login): no longer takes learner_id
from the request at all -- it's resolved from the Authorization bearer
token via app/core/security.py's get_current_learner, same fix as
app/routers/tutor.py.
"""

import asyncio
from datetime import timedelta

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utcnow_naive

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_learner
from app.models import Attachment, Learner
from app.schemas.attachments import AttachmentUploadResponse
from app.services.attachments import (
    MAX_IMAGE_BYTES,
    MAX_UPLOAD_BYTES,
    classify_content_type,
    content_matches_kind,
    extract_docx_text,
    extract_pdf_text,
    save_upload,
)

router = APIRouter(prefix="/attachments", tags=["attachments"])


@router.post("/", response_model=AttachmentUploadResponse)
async def upload_attachment(
    learner: Learner = Depends(get_current_learner),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> Attachment:
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

    # deep scan M4: a daily quota per learner, so uploads can't fill the disk
    recent = (
        await db.execute(
            select(func.count()).select_from(Attachment).where(
                Attachment.learner_id == learner.id, Attachment.created_at >= utcnow_naive() - timedelta(days=1)
            )
        )
    ).scalar_one()
    if recent >= settings.upload_daily_limit:
        raise HTTPException(status_code=429, detail="You've uploaded a lot of files today. Please try again tomorrow.")

    # Read in chunks and stop as soon as the file is too big, instead of
    # reading a huge upload into memory first (deep scan M4).
    chunks, size = [], 0
    while chunk := await file.read(1024 * 1024):
        size += len(chunk)
        if size > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"File too large (max {MAX_UPLOAD_BYTES // (1024 * 1024)}MB).",
            )
        chunks.append(chunk)
    data = b"".join(chunks)
    if not content_matches_kind(data, kind):
        raise HTTPException(status_code=415, detail="That file isn't really the type its name says. Please attach a real photo, PDF or Word file.")
    if kind == "image" and len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=413,
            detail="This photo is too large (max 5MB). Try a smaller photo or a screenshot.",
        )

    storage_path = save_upload(data, file.filename or "upload", settings.upload_dir)

    extracted_text: str | None = None
    extraction_warning: str | None = None
    # deep scan M4: parse in a worker thread with a time limit, so a hostile
    # or broken file can't stall the server
    extractor = extract_pdf_text if kind == "pdf" else extract_docx_text if kind == "docx" else None
    if extractor is not None:
        try:
            extracted_text, extraction_warning = await asyncio.wait_for(asyncio.to_thread(extractor, storage_path), 20)
        except asyncio.TimeoutError:
            extracted_text, extraction_warning = "", "This file took too long to read. Try a photo of each page instead."
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
