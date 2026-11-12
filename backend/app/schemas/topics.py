"""
Pydantic schemas for GET /topics.

NEW 8 Nov 2026, part of step 7 (frontend chat UI). Not a recovery --
this endpoint didn't exist before. It exists specifically so the
frontend can list all 12 seeded CAPS topics for its topic picker,
instead of the recovered api.js's approach of hardcoding a handful of
topic UUIDs from a now-gone database (flagged in REBUILD_SPEC.md
Section 3 as something to fix "on rebuild", with "fetch them
dynamically instead of hardcoding" as the explicitly preferred fix).

FIX 12 Nov 2026 (multi-subject support, ADR-013): added subject_id so
the frontend can group/filter topics by subject now that a second
subject (Physical Sciences) exists -- this field was safe to omit while
there was only ever one subject in the database.
"""

import uuid

from pydantic import BaseModel


class TopicResponse(BaseModel):
    id: uuid.UUID
    subject_id: uuid.UUID
    name: str
    caps_reference: str | None
    prerequisite_id: uuid.UUID | None

    class Config:
        from_attributes = True
