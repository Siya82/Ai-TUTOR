# ADR-002: Personalization — Presentation Preference + Adaptive Pace

**Status:** Accepted
**Date:** 2026-07-31

## Context

The pilot needs learners to feel the tutor adapts to *how* they learn, not
just *what* they get right or wrong — visual vs. practical vs. auditory
explanation styles, and different pacing for learners who need more
scaffolding vs. learners who are moving fast and could handle extension
content ("slower" / "gifted" in the original request).

## Decision: reject fixed learning-style diagnosis, use two independent signals instead

The common approach (VARK-style: diagnose a learner as "a visual learner"
via a quiz, then always teach them visually) was considered and rejected.
The research evidence for the "meshing hypothesis" — that matching
instruction to a diagnosed style improves outcomes — is weak; multiple
controlled studies have failed to find the predicted effect. Building a
diagnostic quiz for this would add engineering effort in service of a
mechanism unlikely to actually help learners.

Instead, personalization is split into two independent, defensible signals:

1. **Presentation preference** — learner-selected, not diagnosed. A toggle
   ("show me diagrams" / "show me worked real-world examples" / "explain it
   like I'm listening"), changeable anytime. This is about learner comfort
   and engagement, not a claim that it improves learning outcomes on its
   own — multiple representations of the same concept are good practice
   regardless.
2. **Pace/difficulty tier** — computed continuously from `Attempt` history
   (rolling accuracy + response time on recent attempts in a topic), not
   asked upfront or fixed. A learner who's fast and accurate gets less
   scaffolding and extension questions; a learner who's struggling gets
   more worked steps and simpler question difficulty. This directly
   reflects demonstrated performance, not a label.

## Consequences

- No new content library needed per "style" — one Claude call per
  explanation, prompt-shaped by these two signals.
- Pace tier is always re-derived from recent attempts, so it can't go
  stale the way a one-time diagnostic label would (a learner who was
  "slower" in Functions can be "on pace" in Trigonometry).
- Presentation preference is explicitly framed to learners as "how do you
  want this explained" rather than "we've determined you're a visual
  learner" — avoids over-claiming and keeps it changeable.
