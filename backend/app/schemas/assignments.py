"""
Pydantic request/response schemas for the Assignments feature, both
the teacher-facing (app/routers/teach_assignments.py) and learner-
facing (app/routers/learner_assignments.py) sides. See
docs/ADR-028-assignments.md.

NEW 15 Nov 2026.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Teacher-facing
# ---------------------------------------------------------------------------


class CustomQuestionCreateRequest(BaseModel):
    topic_id: uuid.UUID
    text: str = Field(min_length=1)
    model_answer: str = Field(min_length=1)


class CustomQuestionResult(BaseModel):
    id: uuid.UUID
    topic_id: uuid.UUID
    text: str
    model_answer: str
    created_at: datetime


class AssignmentCreateRequest(BaseModel):
    title: str = Field(min_length=1)
    instructions: str | None = None
    due_at: datetime | None = None
    question_ids: list[uuid.UUID] = Field(min_length=1)
    learner_ids: list[uuid.UUID] = Field(min_length=1)


class AssignmentSummary(BaseModel):
    id: uuid.UUID
    title: str
    instructions: str | None
    due_at: datetime | None
    created_at: datetime
    question_count: int
    target_count: int


class LearnerCompletionItem(BaseModel):
    learner_id: uuid.UUID
    display_name: str
    status: str  # "not_started" | "in_progress" | "completed"
    answered_count: int
    question_count: int
    correct_count: int


class AssignmentQuestionItem(BaseModel):
    # The teacher-facing question view -- unlike the learner-facing one
    # below, this one DOES include model_answer, since the teacher
    # authored or is reviewing the question, not answering it.
    id: uuid.UUID
    text: str
    model_answer: str
    order_index: int


class AssignmentDetail(BaseModel):
    id: uuid.UUID
    title: str
    instructions: str | None
    due_at: datetime | None
    created_at: datetime
    questions: list[AssignmentQuestionItem]
    completions: list[LearnerCompletionItem]


# ---------------------------------------------------------------------------
# Learner-facing
# ---------------------------------------------------------------------------


class LearnerAssignmentSummary(BaseModel):
    id: uuid.UUID
    title: str
    instructions: str | None
    due_at: datetime | None
    status: str  # "not_started" | "in_progress" | "completed"
    answered_count: int
    question_count: int


class LearnerQuestionItem(BaseModel):
    # NEVER includes model_answer -- a student answering this question
    # must not be able to read the model answer from the same payload
    # that asks them to produce one. See ADR-028's Decision section.
    id: uuid.UUID
    text: str
    order_index: int
    answered: bool
    is_correct: bool | None
    ai_feedback: str | None
    learner_response: str | None


class LearnerAssignmentDetail(BaseModel):
    id: uuid.UUID
    title: str
    instructions: str | None
    due_at: datetime | None
    questions: list[LearnerQuestionItem]


class AnswerSubmitRequest(BaseModel):
    learner_response: str = Field(min_length=1)


class AnswerSubmitResult(BaseModel):
    question_id: uuid.UUID
    is_correct: bool | None
    feedback: str | None
