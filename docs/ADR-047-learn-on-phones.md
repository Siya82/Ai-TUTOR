# ADR-047 — LEARN on a phone

**Date:** 19 Nov 2026 · **Status:** Accepted

## Context

Most learners will use THUTOra on a phone. On a 390px screen the LEARN chat
stacked three things above and below the conversation:
- the whole subject/topic list (up to 35% of the screen);
- a two-row header;
- the symbol keyboard (two or three rows).

That left the conversation about 70px. This was found while filming the
intro video.

## Decision

Up to 760px wide:
- The topic list is a full-screen drawer. A bar under the header shows what
  the learner is studying ("Gr 10 · Pure Mathematics / Algebraic
  Expressions"), and tapping it opens the drawer. Opening a subject keeps
  the drawer open; choosing a topic closes it.
- The header is compact: header buttons show icons only. Their names stay
  available to screen readers, and the learner's name is hidden.
- The symbol keyboard opens from a Σ button next to the paperclip and
  scrolls if it's tall.
- The layout uses `100dvh`, so mobile browser toolbars don't cut off the
  message box.

Wider screens are unchanged: sidebar, full header, keyboard always shown.

## Result

On a 390×844 phone the conversation now gets about 565px, two-thirds of
the screen.
