"""
Pydantic schemas for GET /learners.

NEW 8 Nov 2026, part of step 7. Not a recovery -- this endpoint didn't
exist before. Lets the frontend fetch a real learner id to use instead
of the recovered api.js's hardcoded DEV_LEARNER_ID (a UUID from the
now-gone original database -- same "fetch dynamically instead of
hardcoding" fix REBUILD_SPEC.md recommends for topics).

No authentication yet (step 8, not done) -- consistent with every
other endpoint in this API today (dashboard included). Exposing a
plain list of learners with no access control is acceptable ONLY for
this pre-auth pilot/dev stage; this must not ship as-is once step 8
lands real auth.
"""

import uuid

from pydantic import BaseModel


class LearnerResponse(BaseModel):
    id: uuid.UUID
    display_name: str
    grade: int
    preferred_modality: str

    class Config:
        from_attributes = True
