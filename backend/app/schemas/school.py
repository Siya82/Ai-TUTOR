"""Schemas for the /school/* router (ADR-031, school roles and scoping)."""

import uuid
from typing import Optional

from pydantic import BaseModel, Field


class RoleOut(BaseModel):
    id: uuid.UUID
    role: str
    label: str
    subject_name: Optional[str] = None
    grade: Optional[int] = None


class AllocationOut(BaseModel):
    id: uuid.UUID
    subject_id: uuid.UUID
    subject_name: str
    grade: int
    class_id: uuid.UUID
    class_name: str
    teacher_user_id: Optional[uuid.UUID] = None
    teacher_name: Optional[str] = None


class SchoolMe(BaseModel):
    user_id: uuid.UUID
    display_name: Optional[str]
    staff_number: str
    school_id: uuid.UUID
    school_name: str
    roles: list[RoleOut]
    allocations: list[AllocationOut]
    can_manage_school: bool
    whole_school_academic: bool
    grantable_roles: list[str]
    # Subjects this person may see for at least one learner -- for pickers.
    visible_subject_ids: list[uuid.UUID]
    has_academic_access: bool


class ClassCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    grade: int = Field(ge=1, le=12)


class ClassSummary(BaseModel):
    id: uuid.UUID
    name: str
    grade: int
    member_count: int
    allocations: list[AllocationOut]


class ClassMemberOut(BaseModel):
    learner_id: uuid.UUID
    display_name: str
    grade: int
    student_number: str


class ClassDetail(ClassSummary):
    members: list[ClassMemberOut]


class ClassMembersAdd(BaseModel):
    learner_ids: list[uuid.UUID] = Field(min_length=1)


class StaffCreate(BaseModel):
    display_name: str = Field(min_length=1, max_length=100)
    staff_number: Optional[str] = None


class StaffCreateResult(BaseModel):
    user_id: uuid.UUID
    display_name: str
    staff_number: str
    temp_password: Optional[str]


class StaffOut(BaseModel):
    user_id: uuid.UUID
    display_name: Optional[str]
    staff_number: str
    roles: list[RoleOut]
    allocations: list[AllocationOut]


class RoleGrant(BaseModel):
    role: str
    subject_name: Optional[str] = None
    grade: Optional[int] = Field(default=None, ge=1, le=12)


class AllocationCreate(BaseModel):
    teacher_user_id: uuid.UUID
    subject_id: uuid.UUID
    class_id: uuid.UUID
