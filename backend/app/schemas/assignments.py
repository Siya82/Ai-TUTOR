"""
Pydantic request/response schemas for the Assignments feature, both
the teacher-facing (app/routers/teach_assignments.py) and learner-
facing (app/routers/learner_assignments.py) sides. See
docs/ADR-028-assignments.md and docs/ADR-029-assignment-mode-and-marks.md.

NEW 15 Nov 2026. UPDATED 15 Nov 2026 (ADR-029): added per-question
marks and the practice/test mode + results-release gating.
"""

import uuid
from datetime import datetime
from typing import Literal

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
    # NEW (ADR-029): None for a seeded/CAPS-bank question, set to the
    # authoring teacher's User.id for a custom one -- same column
    # Question.created_by_user_id already carried (ADR-028), now
    # surfaced here so GET /teach/questions (the bank-browsing list)
    # can tell a teacher's own custom question apart from a seeded one
    # without a second round-trip.
    created_by_user_id: uuid.UUID | None = None


class AssignmentQuestionInput(BaseModel):
    """
    One question being attached to a new assignment, with the marks
    it's worth IN THIS ASSIGNMENT (ADR-029) -- replaces the old flat
    `question_ids: list[uuid.UUID]`, since marks is now a per-
    assignment-question fact, not a property of the Question itself.
    """

    question_id: uuid.UUID
    marks: int = Field(default=1, ge=1, le=100)


class AssignmentCreateRequest(BaseModel):
    title: str = Field(min_length=1)
    instructions: str | None = None
    due_at: datetime | None = None
    # NEW (ADR-029). "practice" (default) is this feature's original,
    # only behaviour: AI feedback shows the moment a student answers.
    # "test" withholds it until the teacher releases results -- see
    # Assignment.mode's docstring in app/models/__init__.py.
    mode: Literal["practice", "test"] = "practice"
    questions: list[AssignmentQuestionInput] = Field(min_length=1)
    # UPDATED 17 Nov 2026 (ADR-031): pick individual learners, whole
    # classes, or both -- at least one learner must result (checked in
    # create_assignment(), after classes are expanded).
    learner_ids: list[uuid.UUID] = Field(default_factory=list)
    class_ids: list[uuid.UUID] = Field(default_factory=list)


class AssignmentSummary(BaseModel):
    id: uuid.UUID
    title: str
    instructions: str | None
    due_at: datetime | None
    created_at: datetime
    mode: str
    results_released: bool
    question_count: int
    target_count: int
    marks_total: int


class LearnerCompletionItem(BaseModel):
    learner_id: uuid.UUID
    display_name: str
    status: str  # "not_started" | "in_progress" | "completed"
    answered_count: int
    question_count: int
    correct_count: int
    # NEW (ADR-029). marks_earned sums the marks of every question
    # whose LATEST attempt is correct (get_assignment_completion() now
    # dedupes by latest-attempt-per-question -- a student resubmitting
    # via "Re-submit answer" no longer double-counts). marks_total is
    # the assignment's full point value regardless of how many
    # questions this student has answered yet.
    marks_earned: int
    marks_total: int


class AssignmentQuestionItem(BaseModel):
    # The teacher-facing question view -- unlike the learner-facing one
    # below, this one DOES include model_answer, since the teacher
    # authored or is reviewing the question, not answering it.
    id: uuid.UUID
    text: str
    model_answer: str
    order_index: int
    marks: int


class AssignmentDetail(BaseModel):
    id: uuid.UUID
    title: str
    instructions: str | None
    due_at: datetime | None
    created_at: datetime
    mode: str
    results_released: bool
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
    mode: str
    results_released: bool
    status: str  # "not_started" | "in_progress" | "completed"
    answered_count: int
    question_count: int
    marks_total: int
    # NEW (ADR-029). None while this is a "test"-mode assignment whose
    # results haven't been released yet -- showing a running score
    # would itself leak which answers were right, defeating the whole
    # point of withholding feedback. Always a real number for
    # "practice" mode, and for "test" mode once released.
    marks_earned: int | None


class LearnerQuestionItem(BaseModel):
    # NEVER includes model_answer -- a student answering this question
    # must not be able to read the model answer from the same payload
    # that asks them to produce one. See ADR-028's Decision section.
    id: uuid.UUID
    text: str
    order_index: int
    marks: int
    answered: bool
    is_correct: bool | None
    ai_feedback: str | None
    learner_response: str | None
    # NEW (ADR-029). True when this question has been answered but the
    # mark/feedback are being withheld (mode == "test" and the teacher
    # hasn't released results yet) -- lets the frontend show "Submitted
    # -- awaiting release" instead of silently looking unmarked.
    feedback_withheld: bool = False


class LearnerAssignmentDetail(BaseModel):
    id: uuid.UUID
    title: str
    instructions: str | None
    due_at: datetime | None
    mode: str
    results_released: bool
    questions: list[LearnerQuestionItem]


class AnswerSubmitRequest(BaseModel):
    learner_response: str = Field(min_length=1)


class AnswerSubmitResult(BaseModel):
    question_id: uuid.UUID
    # NEW (ADR-029). The question's point value -- always shown, even
    # when withheld, same reasoning as a real exam printing "[5 marks]"
    # next to a question before it's marked.
    marks: int
    is_correct: bool | None
    feedback: str | None
    feedback_withheld: bool = False
