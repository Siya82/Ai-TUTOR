# ADR-013: Multi-subject support -- Physical Sciences added, Chemistry strand deferred

**Status:** Accepted
**Date:** 2026-11-12

## Context

`THUTOra_Project_Report.md`'s "Brand & scope reconciliation" section
flagged an explicit open decision: the THUTOra brand materials depict
a four-subject app (Mathematics, Physical Sciences, Life Sciences,
Accounting), while ADR-006 deliberately narrowed engineering scope to
Grade 10 Pure Mathematics only, on a depth-over-breadth bet. That ADR
paused (not discarded) Physical Science work, built as subject-agnostic
patterns where possible.

Siya asked directly whether Science and Technology could be added now,
in parallel with the step 8 (authentication) work already in progress,
given the broader EdPaaS vision (Students/Teachers/Parents/DoE). This
ADR records the resulting scoping decision before any schema or code
changed.

Two things were true before this ADR and mattered to the decision:

1. The database schema was never actually Maths-hardcoded --
   `subjects` and `topics` have had a real `Topic.subject_id` foreign
   key since the original 11-table design. Adding a second subject row
   needed no migration.
2. The tutoring *engine* was hardcoded, in three places: `tutor.py`'s
   system prompt literally said "Mathematics tutor" regardless of
   topic; `seed_dev_data.py` had a single module-level
   `SUBJECT_NAME`/`GRADE` pair; and MathGuard (ADR-011's protected
   differentiator) only verifies equation-shaped content via sympy --
   it has nothing to check in purely descriptive/conceptual content.

## Decision

Add **Physical Sciences, Grade 10, Physics strand only** as the second
subject: Vectors in Two Dimensions, Motion in One Dimension, Mechanical
Energy, Waves/Sound/Light, Electromagnetic Radiation, Magnetism,
Electrostatics, Electric Circuits (8 topics, CAPS-aligned, sourced from
the DBE CAPS Physical Sciences document and corroborated against two
independent topic-list sources, checked 12 Nov 2026).

**Explicitly deferred:** the Chemistry strand (Matter and Materials,
Chemical Change, Chemical Systems) and "Technology" as its own subject.
Reasoning:

- CAPS "Technology" is a Grades 7-9 subject; from Grade 10 it splits
  into subjects like Physical Sciences, EGD, or CAT. Since engineering
  scope is Grade 10, there is no single "Technology" subject to add at
  this grade -- Physical Sciences is the actual Grade-10-appropriate
  next subject, not a generic "Science and Technology" pairing.
- The Physics strand is equation-shaped the same way Maths is (F=ma,
  v=u+at, V=IR, Coulomb's Law, etc.) -- MathGuard's sympy-based
  verification extends to it directly, the same protected
  differentiator, not a weaker one.
- Most of the Chemistry strand is not equation-shaped in that sense
  (classification, bonding, balancing reactions). Seeding it now would
  mean shipping tutoring with no real correctness guarantee for that
  content, undermining rather than extending the "self-verified"
  differentiator. Revisit once there is an actual plan for verifying
  (or explicitly flagging as unverified) non-equation content, rather
  than silently shipping unverified alongside verified.

This mirrors ADR-006's own depth-over-breadth reasoning, applied one
level down: breadth into a second subject, but only the slice of it
that keeps the differentiator intact.

## Implementation

- `tutor.py`: `build_tutor_system_prompt()` now takes `subject_name`/
  `grade` (defaulting to the original Pure Mathematics values) instead
  of a hardcoded "Mathematics" string; the RAG-grounding placeholder
  became a function of the same two values.
- `tutor_orchestration.py`: reads `recommended_topic.subject.name`/
  `.grade` to build the prompt -- requires the caller to have
  eager-loaded `Topic.subject`, since this module is deliberately
  DB-free.
- `routers/tutor.py`: both `Topic` fetches in the prerequisite-chain
  walk now use `selectinload(Topic.subject)`.
- `seed_dev_data.py`: generalized from one hardcoded subject to a
  `SUBJECTS` list of self-contained specs; added the Physical Sciences
  Physics-strand topics and two diagnostic questions each.
- New `GET /subjects` endpoint (`schemas/subjects.py`,
  `routers/subjects.py`), mirroring the existing `/topics`,
  `/learners` pattern. `TopicResponse` gained `subject_id` so the
  frontend can filter.
- Frontend: new `SubjectPicker.jsx`; `ChatScreen.jsx` fetches subjects,
  defaults to Pure Mathematics (preserving the existing default
  experience) when seeded, filters the topic list to the selected
  subject, and resets the topic when the subject changes.
  `SymbolKeyboard.jsx` gained topic-specific symbol sets for all 8 new
  topics (→, Δ, λ, Ω, Hz, etc.), same pattern as the existing Maths
  entries.

## Consequences

- **Update 13 Nov 2026:** the first real pytest run after this change
  found a genuine (if mundane) regression before the anticipated
  MathGuard one below ever got a chance to surface: 4 tests in
  `test_tutor_orchestration.py` failed with `AttributeError:
  'NoneType' object has no attribute 'name'`, because that test file's
  own `_topic()` helper builds detached `Topic` objects with no DB
  session, so `.subject` was never populated -- unlike the real
  `routers/tutor.py` caller, which eager-loads it. Fixed by having the
  helper attach a real in-memory `Subject`, matching the contract this
  ADR's own Implementation section describes, rather than weakening
  that contract to paper over a test fixture gap. See BUILD_LOG.md's
  13 Nov 2026 entry.
- MathGuard has not yet been live-tested against real Physics content
  (units like "m/s" or "N" written inline, rather than inside a $$...$$
  block, are a plausible new parsing edge the Maths-only gap list never
  had to consider) -- expect the same "find a real gap via a live call,
  fix it, add a regression test" pattern ADR-011/REBUILD_SPEC Section 1
  already documents for Maths, repeated for Physics.
- `THUTOra_Project_Report.md`'s "Brand & scope reconciliation" open
  decision is now partially resolved (Physical Sciences: yes, Physics
  strand now / Chemistry strand later) and should be updated to reflect
  that rather than left as fully open.
- Life Sciences and Accounting remain entirely out of scope -- not
  evaluated by this ADR at all, since neither was part of the question
  that prompted it.
