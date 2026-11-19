# ADR-036: Teacher "Today" panel

**Date:** 19 Nov 2026 · **Status:** Accepted

## Context
SamarthX gets daily use because teachers check in every morning. THUTOra
needs a daily reason for teachers to open it, and that reason should be
learning, not admin.

## Decision
A first tab, **Today** (default for anyone with academic access), built from
the last 7 days of marked answers, scoped exactly like the Progress tab:
- **Needs help:** a learner with at least 2 wrong answers on a topic, and
  wrong at least half the time.
- **Weakest topics** (lowest accuracy first, top 5), each with **Send
  practice**: a 5-question practice assignment for just the learners who got
  it wrong, preferring bank questions they haven't answered correctly in 30 days.
- **Due soon:** the teacher's own assignments due within 3 days, with how many
  learners haven't finished.
- **Haven't practised this week.**

Rules live in `app/services/teacher_today.py` (pure, unit-tested); endpoints
in `app/routers/teacher_today.py`.
