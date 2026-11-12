"""
Pydantic schema for GET /subjects.

NEW 12 Nov 2026, part of multi-subject support (ADR-013). Didn't exist
before because there was only ever one subject (Pure Mathematics) --
the frontend's topic picker just listed every topic directly. Now that
Physical Sciences exists too, the frontend needs a subject list first
so it can offer a subject selector before (or alongside) the topic
picker.
"""

import uuid

from pydantic import BaseModel


class SubjectResponse(BaseModel):
    id: uuid.UUID
    name: str
    grade: int

    class Config:
        from_attributes = True
