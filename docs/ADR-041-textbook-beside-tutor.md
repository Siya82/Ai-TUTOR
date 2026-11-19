# ADR-041: The topic's textbook chapter beside the tutor chat

**Date:** 19 Nov 2026 · **Status:** Accepted (Siya: "combine library and tutor")

## Context
The Library (ADR-032) and the tutor chat were separate views. Each book
import already maps topics to page/section ranges (`book_topic_ranges`), so
the chat can show the right chapter for whatever topic the learner picks.

## Decision
- `GET /books/for-topic/{topic_id}`: the chapter(s) linked to a topic,
  limited to books at or below the learner's grade (same rule as the
  Library). Best match first: the topic's own grade, ePub before PDF, then
  the fullest range.
- In Tutor chat, a **Textbook** panel opens beside the conversation with
  that chapter (e.g. Algebraic Expressions → "Chapter 1: Algebraic
  expressions", Everything Maths Grade 10). Navigation stays inside the
  chapter; "Open in Library" opens the whole book.
- "Ask THUTOra about this section" / "Ask about what I highlighted" puts the
  book chip straight into the chat beside it, so the question carries the
  exact passage and equations (ADR-032 context).
- Open by default on wide screens, remembered per device; on phones it opens
  over the chat and closes itself after "Ask".
- `BookReader` is reused with a `range` prop; no second reader to maintain.

## Later
Teachers could get the same chapter beside the question bank when setting
assignments (TEACH has no chat, so it isn't included here).
