"""
NEW 19 Nov 2026 (ADR-038, CONNECT -- parents).

Pure helpers for the parent view:

- child_overview(): a parent-friendly picture of one child from their marked
  answers and assignments -- how much they practised this week, how often
  they were right, their strongest and weakest topics, and their work. A
  Test's marks only appear once the teacher has released them (same rule
  the learner sees, ADR-029). Tutor conversations are never shown to
  parents: they're the learner's own space.
- summary_text(): the same picture as a few plain English sentences, which
  the router may translate into the parent's language with Claude.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

WEEK_DAYS = 7
TOPIC_WINDOW_DAYS = 60
MIN_ANSWERS_FOR_TOPIC = 3


@dataclass(frozen=True)
class MarkedAnswer:
    topic_id: UUID
    topic_name: str
    subject_name: str
    is_correct: bool
    created_at: datetime


@dataclass(frozen=True)
class WorkItem:
    title: str
    subject_names: tuple[str, ...]
    mode: str
    due_at: datetime | None
    status: str  # not_started | in_progress | completed
    marks_earned: int | None  # None when hidden (unreleased test)
    marks_total: int


def child_overview(first_name: str, answers: list[MarkedAnswer], work: list[WorkItem], now: datetime) -> dict:
    week = [a for a in answers if a.created_at >= now - timedelta(days=WEEK_DAYS)]
    window = [a for a in answers if a.created_at >= now - timedelta(days=TOPIC_WINDOW_DAYS)]

    per_topic: dict[UUID, list[MarkedAnswer]] = defaultdict(list)
    for a in window:
        per_topic[a.topic_id].append(a)
    topics = []
    for items in per_topic.values():
        if len(items) < MIN_ANSWERS_FOR_TOPIC:
            continue
        right = sum(1 for a in items if a.is_correct)
        topics.append(
            {
                "topic_name": items[0].topic_name,
                "subject_name": items[0].subject_name,
                "answered": len(items),
                "accuracy": round(100 * right / len(items)),
            }
        )
    topics.sort(key=lambda t: (t["accuracy"], -t["answered"]))
    weakest = topics[:3]
    strongest = sorted([t for t in topics if t not in weakest], key=lambda t: -t["accuracy"])[:3]

    week_right = sum(1 for a in week if a.is_correct)
    outstanding = [
        w for w in work if w.status != "completed" and (w.due_at is None or w.due_at >= now - timedelta(days=14))
    ]
    return {
        "first_name": first_name,
        "week": {
            "answered": len(week),
            "accuracy": round(100 * week_right / len(week)) if week else None,
            "active_days": len({a.created_at.date() for a in week}),
        },
        "weakest_topics": weakest,
        "strongest_topics": strongest,
        "work": [
            {
                "title": w.title,
                "subjects": list(w.subject_names),
                "mode": w.mode,
                "due_at": w.due_at.isoformat() if w.due_at else None,
                "status": w.status,
                "marks_earned": w.marks_earned,
                "marks_total": w.marks_total,
            }
            for w in work
        ],
        "outstanding_count": len(outstanding),
    }


def summary_text(overview: dict) -> str:
    name = overview["first_name"]
    week = overview["week"]
    parts = []
    if week["answered"] == 0:
        parts.append(f"{name} didn't answer any practice questions in THUTOra this week.")
    else:
        parts.append(
            f"This week {name} answered {week['answered']} question"
            f"{'' if week['answered'] == 1 else 's'} on {week['active_days']} day"
            f"{'' if week['active_days'] == 1 else 's'}, and got {week['accuracy']}% right."
        )
    if overview["strongest_topics"]:
        best = overview["strongest_topics"][0]
        parts.append(f"{name} is doing well in {best['topic_name']} ({best['subject_name']}).")
    if overview["weakest_topics"]:
        weak = overview["weakest_topics"][0]
        parts.append(
            f"{weak['topic_name']} ({weak['subject_name']}) needs more practice -- "
            f"about {weak['accuracy']}% right so far."
        )
    if overview["outstanding_count"]:
        n = overview["outstanding_count"]
        parts.append(f"{name} has {n} piece{'' if n == 1 else 's'} of school work still to finish.")
    else:
        parts.append(f"{name} has no unfinished school work in THUTOra.")
    parts.append("A few minutes of practice each day makes a real difference.")
    return " ".join(parts)


TRANSLATE_SYSTEM_PROMPT = (
    "You translate short school progress messages for South African parents. Translate the user's "
    "message into {language}, in warm, plain, everyday language a parent would use. Keep names, "
    "numbers and percentages exactly as they are. Keep school subject and topic names in English "
    "in brackets after your translation of them, e.g. 'izibalo (Mathematics)'. Reply with the "
    "translation only."
)
