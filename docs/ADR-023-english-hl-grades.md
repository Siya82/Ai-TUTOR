# ADR-023: Scale English Home Language to Grade 11 and Grade 12 (isiZulu paused)

**Status:** Accepted
**Date:** 15 November 2026

## Context

Siya's explicit direction this session: pause isiZulu Home Language work --
ADR-021's RAG content-ingestion pipeline (built to address a real, confirmed
isiZulu accuracy failure) is mid-flight and deliberately not touched here --
and proceed with the rest of the Grade 11/12 scale-up, which includes English
Home Language. isiZulu Home Language Grade 11/12 are therefore explicitly NOT
built in this pass; this is a deliberate scope decision, not an oversight,
and isiZulu's own open item (native-speaker content review, ADR-020) remains
exactly as open as before.

Checked the DBE's own CAPS Home Language document again before writing any
seed data (checked 15 Nov 2026): confirmed the same four CAPS skill strands
(Listening and Speaking, Reading and Viewing, Writing and Presenting, Language
Structures and Conventions) apply at every FET grade, not just Grade 10 --
what changes per grade is complexity (comprehension passage length, 500-600
words at Grade 10 rising to 700-800 at Grade 12; poem count, 10 at Grade 10/11
rising to 12 at Grade 12; essay length), not the skill structure itself.

## Decision

**Reuse the exact same 5-topic template ADR-020 established at Grade 10, for
both Grade 11 and Grade 12** -- the architecture was already built to
generalize this way (ADR-020's own Open items explicitly named "Grade 11/12
Home Languages don't exist yet" as a known future step, not an unresolved
question). Each grade's root topic (Language Structures and Conventions)
cross-grade-anchors to the previous grade's exact-name version -- the same
escalating-chain shape every other subject already uses across its own grades
(Pure Mathematics, Physical Sciences, Accounting) -- and the other four topics
chain within-grade exactly as Grade 10 did (Listening and Speaking -> Reading
and Viewing: Literature -> Reading and Viewing: Visual and Media Texts ->
Writing and Presenting).

**Content deepens per grade, matching the real CAPS complexity escalation
confirmed above, not just relabeled Grade 10 content.** Grade 11 questions
move from simple figure-of-speech identification to features of formal
register and dramatic technique (soliloquy, camera angle, discursive-essay
structure). Grade 12 questions move to more advanced literary/rhetorical
devices (paradox, dramatic irony, enjambment, juxtaposition/satire,
argumentative vs. discursive essay structure) -- genuinely harder content, not
the same questions with a grade number changed.

**Verification and literature-content stance unchanged from ADR-020:** still
no MathGuard-style checking (no equation- or ledger-shaped content exists in
this subject at any grade); literature topics stay genre-general rather than
naming a specific prescribed text, for the same reason ADR-020 gave (the real
current prescribed-text list comes from a periodically-revised DBE circular
not reliably known here, and guessing a title risks teaching to a text no
longer prescribed).

**isiZulu Home Language Grade 11/12 do not exist after this change.** Not an
oversight -- Siya's explicit choice this session, separate from and not
resolving ADR-020's still-open isiZulu content-review item or ADR-021's
still-in-progress RAG ingestion work.

## Consequences

- `backend/scripts/seed_dev_data.py`: two new `SUBJECTS` entries (English Home
  Language grade 11, grade 12), each with its own
  `_ENGLISH_HL_GRADE1{1,2}_TOPICS`/`_QUESTIONS` pair (5 topics, 10 questions
  each). No model or migration change.
- `frontend/src/components/SymbolKeyboard.jsx`: zero new entries needed --
  Home Language topics never had entries at any grade (ADR-020's own decision;
  an unmatched topic name falls back to `COMMON_SYMBOLS`, which is harmless for
  essay-writing topics), and both new grades reuse the exact same 5 topic
  names, confirmed by the same cross-check script used for ADR-022.
- `app/services/tutor.py`, `app/routers/topics.py`,
  `frontend/src/components/SubjectTopicSidebar.jsx`: zero changes, confirmed
  by reading the code, same finding as every prior addition.

## Open items (explicitly not done, not silently dropped)

- **isiZulu Home Language Grade 11/12 do not exist.** Deliberately paused per
  Siya's own direction this session -- revisit once ADR-021's isiZulu
  accuracy/RAG-ingestion work is in a workable state, per his own "pick that
  up later" framing.
- **isiZulu Home Language Grade 10's own content-review item (ADR-020) is
  unchanged and still open** -- this ADR does not touch it either way.
- **No current prescribed-text list for English Home Language at any grade**
  -- unchanged from ADR-020.
- **Not live-tested against a real Claude call yet** -- handed to Siya next,
  same discipline as every prior content addition.
- **No rubric-scoring infrastructure for essay-type questions** -- unchanged
  from ADR-020.
