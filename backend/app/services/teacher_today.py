"""
NEW 19 Nov 2026 (ADR-036, teacher "Today" panel).

A daily reason for a teacher to open THUTOra: in one screen, from the
answers their own learners gave over the last few days,

  - who needs help (repeated wrong answers on the same topic),
  - which topics the class is getting wrong most,
  - who hasn't practised at all recently,
  - their own assignments due soon and how many learners are still behind,

with a one-click "practice set" on any weak topic for exactly the learners
who struggled (see make_practice_question_ids).

The functions here are pure (no database), like class_progress.py, so the
rules are unit-tested directly; app/routers/teacher_today.py does the
three or four queries and calls them.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from uuid import UUID

WINDOW_DAYS = 7
NEEDS_HELP_MIN_WRONG = 2
MAX_WEAK_TOPICS = 5
PRACTICE_SET_SIZE = 5


@dataclass(frozen=True)
class Answer:
    learner_id: UUID
    question_id: UUID
    topic_id: UUID
    is_correct: bool
    created_at: datetime


@dataclass
class TopicInfo:
    id: UUID
    name: str
    subject_name: str
    grade: int


@dataclass
class HelpItem:
    learner_id: UUID
    learner_name: str
    topic_id: UUID
    topic_name: str
    subject_name: str
    wrong: int
    answered: int


@dataclass
class WeakTopic:
    topic_id: UUID
    topic_name: str
    subject_name: str
    grade: int
    wrong: int
    answered: int
    learner_ids: list[UUID] = field(default_factory=list)

    @property
    def accuracy(self) -> int:
        return round(100 * (self.answered - self.wrong) / self.answered) if self.answered else 0


def summarise_today(
    learners: dict[UUID, str],
    answers: list[Answer],
    topics: dict[UUID, TopicInfo],
    now: datetime,
) -> dict:
    """
    learners: id -> name, only the learners this teacher may see academically.
    answers: marked answers by those learners (any age; filtered to the window here).
    """
    since = now - timedelta(days=WINDOW_DAYS)
    recent = [a for a in answers if a.created_at >= since and a.learner_id in learners and a.topic_id in topics]

    per_learner_topic: dict[tuple[UUID, UUID], list[Answer]] = defaultdict(list)
    per_topic: dict[UUID, list[Answer]] = defaultdict(list)
    for a in recent:
        per_learner_topic[(a.learner_id, a.topic_id)].append(a)
        per_topic[a.topic_id].append(a)

    needs_help: list[HelpItem] = []
    for (lid, tid), items in per_learner_topic.items():
        wrong = sum(1 for a in items if not a.is_correct)
        if wrong >= NEEDS_HELP_MIN_WRONG and wrong * 2 >= len(items):  # mostly wrong, and more than once
            t = topics[tid]
            needs_help.append(
                HelpItem(lid, learners[lid], tid, t.name, t.subject_name, wrong, len(items))
            )
    needs_help.sort(key=lambda h: (-h.wrong, h.learner_name))

    weak: list[WeakTopic] = []
    for tid, items in per_topic.items():
        wrong_by = {a.learner_id for a in items if not a.is_correct}
        wrong = sum(1 for a in items if not a.is_correct)
        if wrong == 0:
            continue
        t = topics[tid]
        weak.append(WeakTopic(tid, t.name, t.subject_name, t.grade, wrong, len(items), sorted(wrong_by, key=str)))
    weak.sort(key=lambda w: (w.accuracy, -w.wrong))
    weak = weak[:MAX_WEAK_TOPICS]

    active = {a.learner_id for a in recent}
    quiet = sorted((lid for lid in learners if lid not in active), key=lambda lid: learners[lid])

    return {
        "window_days": WINDOW_DAYS,
        "learner_count": len(learners),
        "active_count": len(active),
        "needs_help": [
            {
                "learner_id": str(h.learner_id),
                "learner_name": h.learner_name,
                "topic_id": str(h.topic_id),
                "topic_name": h.topic_name,
                "subject_name": h.subject_name,
                "wrong": h.wrong,
                "answered": h.answered,
            }
            for h in needs_help
        ],
        "weak_topics": [
            {
                "topic_id": str(w.topic_id),
                "topic_name": w.topic_name,
                "subject_name": w.subject_name,
                "grade": w.grade,
                "wrong": w.wrong,
                "answered": w.answered,
                "accuracy": w.accuracy,
                "learner_ids": [str(x) for x in w.learner_ids],
            }
            for w in weak
        ],
        "quiet_learners": [{"learner_id": str(lid), "learner_name": learners[lid]} for lid in quiet],
    }


def make_practice_question_ids(
    candidate_ids: list[UUID],
    recently_correct: set[UUID],
    size: int = PRACTICE_SET_SIZE,
) -> list[UUID]:
    """
    Picks the practice set: bank questions on the topic, preferring ones
    these learners have NOT recently got right (so they practise what they
    don't know yet), topped up with the rest if the topic is small.
    """
    fresh = [q for q in candidate_ids if q not in recently_correct]
    rest = [q for q in candidate_ids if q in recently_correct]
    return (fresh + rest)[:size]
