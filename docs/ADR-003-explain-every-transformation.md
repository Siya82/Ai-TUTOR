# ADR-003: Every Transformation Must Be Explained (Why, Not Just What)

**Status:** Accepted
**Date:** 2026-07-31

## Context

The pilot's core differentiator from a plain answer-checker or generic
chatbot is that it teaches *why* each step is valid, not just *what* the
next step is. A learner solving `2x + 5 = 15` should understand why
subtracting 5 from both sides is legitimate (preserves equality) and why
dividing by 2 isolates x — not just memorise the sequence of moves.

## Decision

The tutor system prompt encodes this as a **non-negotiable rule**, anchored
by a worked example (`2x + 5 = 15`) directly in the prompt so the model has
a concrete calibration point for the expected depth, rather than a vague
instruction like "explain clearly."

Follow-up "why?" questions are handled by re-explaining the specific step
differently (not repeating verbatim) and, on a second "why?", checking
whether the learner is actually asking about a more foundational concept
(e.g. "why does doing the same thing to both sides work at all?").

Conversations persist as `TutorSession` + `TutorMessage` rows so a "why?"
follow-up is answered with full context of what was already said, not as
an isolated question.

## Consequences

- Slightly higher token cost per response than an answer-only tutor — an
  accepted tradeoff given this is the product's actual value proposition.
- Prompt quality is the single highest-leverage thing to iterate on here;
  the worked example in the prompt should be revisited once real learner
  transcripts show where explanations are too shallow or too verbose.
- Multi-turn persistence means conversation history grows the prompt over
  a long session — worth watching context length in practice; may need
  a summarization strategy for very long sessions later.
