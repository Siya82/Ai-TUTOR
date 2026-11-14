"""
Pydantic request/response schemas for POST /auth/login, GET /auth/me,
and POST /auth/change-password. See docs/ADR-017-student-login.md.
"""

import uuid

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    school_id: uuid.UUID
    student_number: str = Field(min_length=1)
    password: str = Field(min_length=1)


class LearnerProfile(BaseModel):
    id: uuid.UUID
    display_name: str
    grade: int
    preferred_modality: str


class SchoolProfile(BaseModel):
    id: uuid.UUID
    name: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    must_change_password: bool
    learner: LearnerProfile
    school: SchoolProfile


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1)
    # Longer minimum than a typical temp password's own length (10) is
    # unnecessary here -- 8 matches common practice and is enforced
    # client-side too; this is the real (server-side) floor.
    new_password: str = Field(min_length=8)


class MeResponse(BaseModel):
    learner: LearnerProfile
    school: SchoolProfile
    must_change_password: bool
