"""Schemas for /books (ADR-032)."""

import uuid
from typing import Optional

from pydantic import BaseModel, Field


class BookSummary(BaseModel):
    id: uuid.UUID
    title: str
    subject_id: uuid.UUID
    subject_name: str
    grade: int
    publisher: Optional[str]
    licence: str
    attribution: str
    page_count: int
    file_available: bool


class BookTopicRangeOut(BaseModel):
    topic_id: uuid.UUID
    topic_name: str
    start_page: int
    end_page: int


class BookDetail(BookSummary):
    source_url: Optional[str]
    topic_ranges: list[BookTopicRangeOut]


class BookPageOut(BaseModel):
    book_id: uuid.UUID
    page_number: int
    page_count: int
    text: str
    has_text: bool
    topic_id: Optional[uuid.UUID]
    topic_name: Optional[str]
    attribution: str


class BookContext(BaseModel):
    """Sent with POST /tutor/message when the learner asks from the reader.
    The server loads the page text itself; only the highlight comes from the client."""

    book_id: uuid.UUID
    page_number: int = Field(ge=1)
    selected_text: Optional[str] = Field(default=None, max_length=4000)
