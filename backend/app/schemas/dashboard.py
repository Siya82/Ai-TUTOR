"""
Pydantic response schemas for the teacher dashboard API.

RECOVERY NOTE: this module is imported by app/routers/dashboard.py
("from app.schemas.dashboard import ...") but was missing from the
original recovery pass -- it was never read verbatim. Reconstructed here
directly from the exact dict shapes app/services/dashboard.py and
app/services/risk_assessment.py build and return, so field names/types
are inferred from that source code, not recovered verbatim. Re-check
against the real originals if they ever resurface.
"""

from typing import List, Optional

from pydantic import BaseModel


class LearnerSummary(BaseModel):
    id: str
    name: str
    grade: int
    total_attempts: int
    overall_accuracy: Optional[float] = None
    last_activity: Optional[str] = None


class DashboardOverviewResponse(BaseModel):
    learners: List[LearnerSummary]
    total_learners: int


class TopicMastery(BaseModel):
    topic_id: str
    topic_name: str
    subject_name: Optional[str] = None  # NEW 17 Nov 2026 (ADR-030)
    grade: Optional[int] = None  # NEW 17 Nov 2026 (ADR-030)
    attempt_count: int
    accuracy: Optional[float] = None
    last_attempt: Optional[str] = None


class Misconception(BaseModel):
    topic: str
    question: str
    feedback: str


class LearnerMasteryResponse(BaseModel):
    learner_id: str
    topics: List[TopicMastery]
    recent_misconceptions: List[Misconception]


class RiskAssessmentResponse(BaseModel):
    learner_id: str
    topic_id: str
    topic_name: str
    subject_name: Optional[str] = None  # NEW 17 Nov 2026 (ADR-030)
    grade: Optional[int] = None  # NEW 17 Nov 2026 (ADR-030)
    risk_level: str
    factors: List[str]
    interventions: List[str]


class LearnerBasicInfo(BaseModel):
    id: str
    name: str
    grade: int


class LearnerDetailResponse(BaseModel):
    learner: LearnerBasicInfo
    mastery: LearnerMasteryResponse
    risk_assessments: List[RiskAssessmentResponse]


# ---------------------------------------------------------------------------
# NEW 17 Nov 2026 (ADR-030, class progress dashboard) -- GET /dashboard/progress
# Shapes mirror app/services/class_progress.py's summarize_class_progress().
# ---------------------------------------------------------------------------

class FlaggedTopic(BaseModel):
    topic_id: str
    topic_name: str
    risk_level: str


class ClassProgressLearner(BaseModel):
    id: str
    name: str
    grade: int
    total_attempts: int
    overall_accuracy: Optional[float] = None
    last_activity: Optional[str] = None
    risk_level: Optional[str] = None  # None = no attempts yet, deliberately not "low"
    flagged_topics: List[FlaggedTopic]


class ClassProgressTopic(BaseModel):
    topic_id: str
    topic_name: str
    subject_name: str
    grade: int
    learners_attempted: int
    attempt_count: int
    accuracy: Optional[float] = None
    struggling_learners: int


class ClassProgressSummary(BaseModel):
    total_learners: int
    active_learners: int
    learners_with_no_attempts: int
    high_risk_learners: int
    medium_risk_learners: int
    class_accuracy: Optional[float] = None
    active_window_days: int


class ClassProgressResponse(BaseModel):
    grade: Optional[int] = None
    available_grades: List[int]
    summary: ClassProgressSummary
    learners: List[ClassProgressLearner]
    topics: List[ClassProgressTopic]
