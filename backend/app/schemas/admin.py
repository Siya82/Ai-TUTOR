"""
Pydantic request/response schemas for the teacher-only admin API --
single and bulk student provisioning, and the school's student roster.
See docs/ADR-024-teacher-dashboard-and-provisioning.md.

NEW 15 Nov 2026.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class StudentCreateRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=100)
    grade: int = Field(ge=1, le=12)
    # Left blank to auto-generate (the same collision-checked generator
    # provision_student() already used) -- a teacher only has to supply
    # one if their school issues its own student numbers.
    student_number: str | None = Field(default=None, max_length=50)


class StudentCreateResult(BaseModel):
    user_id: uuid.UUID
    learner_id: uuid.UUID
    display_name: str
    grade: int
    student_number: str
    # Only ever present once -- the moment this response is sent back is
    # the only point the plaintext temp password exists outside the
    # student's own head (same posture as provision_student() itself,
    # ADR-017). None when the caller supplied its own password, which
    # this API never does, but kept optional for symmetry with the
    # underlying service function.
    temp_password: str | None = None


class BulkStudentRowError(BaseModel):
    row: int  # 0 for a whole-file problem (missing columns, empty file); otherwise the CSV row number, header counted as row 1
    message: str


class BulkStudentUploadResponse(BaseModel):
    created: list[StudentCreateResult]
    errors: list[BulkStudentRowError]


class StudentRosterItem(BaseModel):
    learner_id: uuid.UUID
    user_id: uuid.UUID
    display_name: str
    grade: int
    student_number: str
    created_at: datetime
    # NEW 17 Nov 2026 (ADR-031): names of the classes this learner is in
    classes: list[str] = []
    is_active: bool = True  # code review #13
    has_consent: bool = False  # ADR-037: an active parent/guardian consent is on record
