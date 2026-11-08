"""
Pydantic schemas for GET /topics.

NEW 8 Nov 2026, part of step 7 (frontend chat UI). Not a recovery --
this endpoint didn't exist before. It exists specifically so the
frontend can list all 12 seeded CAPS topics for its topic picker,
instead of the recovered api.js's approach of hardcoding a handful of
topic UUIDs from a now-gone database (flagged in REBUILD_SPEC.md
Section 3 as something to fix "on rebuild", with "fetch them
dynamically instead of hardcoding" as the explicitly preferred fix).
"""

import uuid

from pydantic import BaseModel


class TopicResponse(BaseModel):
    id: uuid.UUID
    name: str
    caps_reference: str | None
    prerequisite_id: uuid.UUID | None

    class Config:
        from_attributes = True
