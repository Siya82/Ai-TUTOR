# ADR-015: Grade 11 Physical Sciences added (Physics strand)

**Status:** Accepted
**Date:** 2026-11-13

## Context

ADR-014 added Grade 11 Pure Mathematics and, along the way, built a
general cross-grade prerequisite mechanism in `seed_dev_data.py`. Siya
asked directly to add Physical Sciences too, continuing the same
"deepen the equation-verifiable subjects" direction rather than
widening into Chemistry/Life Sciences/Accounting (still out of scope,
per ADR-013's boundary).

## Decision

Add **Physical Sciences, Grade 11, Physics strand only** (matching
ADR-013's own existing scope boundary for Grade 10) as a fourth
`Subject` row. 6 topics, sourced from the DBE CAPS FET Physical
Sciences Grades 10-12 document, Section 3.2 (Grade 11 Annual Teaching
Plan):

**Mechanics chain:** Vectors in Two Dimensions -> Newton's Laws ->
Newton's Universal Law of Gravitation.
**Electricity & Magnetism chain:** Electrostatics -> Electromagnetism
-> Electric Circuits.

Grade 11 drops the Waves/Sound/Light strand entirely (it resumes in
Grade 12) -- 6 topics, not Grade 10's 8.

### Cross-grade prerequisites -- an inexact mapping, unlike Grade 11 Maths

ADR-014 found every Grade 11 Maths topic maps 1:1 onto its Grade 10
counterpart. Physical Sciences does not: only **Vectors in Two
Dimensions** and **Electrostatics** have an exact-name Grade 10
equivalent, so only those two get a direct cross-grade prerequisite
edge (the same "root topics anchor cross-grade, the rest chain
within-grade" pattern ADR-014 already established). The other four
topics chain within-grade only, for two different reasons:

- **Newton's Laws** and **Newton's Universal Law of Gravitation** are
  genuinely new content -- forces/dynamics and gravitation are never
  taught in Grade 10 Physical Sciences at all. There is no Grade 10
  topic to link to, not even an inexact one.
- **Electromagnetism**'s only candidate Grade 10 link, Magnetism, is
  purely descriptive there (poles, attraction/repulsion) while
  Electromagnetism here is quantitative (flux, Faraday's/Lenz's law) --
  judged too inexact a match to wire as a direct prerequisite edge, so
  it chains to Electrostatics (within-grade) instead.

This is the first real test of ADR-014's cross-grade mechanism against
a subject where the mapping ISN'T clean, and it held up without
needing any schema or seed-script changes -- a subject-spec's topic
tuples simply use a plain string (no cross-grade edge) for these four,
exactly as Grade 10's own topics already do for their own root topics.

## Parsing gaps found (proactively, before any live test, before this content was even written)

Research flagged two plausible notational risks going in (scientific
notation with a negative exponent, for the gravitational constant;
Greek `\Delta`/`\Phi` symbols, for Faraday's law) -- both checked in a
sandbox and found to already work fine with the existing pipeline. But
the same sandbox pass, checking a realistic flux formula
(`\Phi = BA\cos\theta`), surfaced two different, more serious gaps
neither research pass nor the brief had specifically anticipated:

- **Gap 20:** `\cos\theta` (trig applied directly to a bare angle
  symbol, no space, no parens) -- a pattern this tutor's own live
  output already uses (the Grade 10 Vectors worked example literally
  wrote `d\cos\theta`). Mangled into a nonsense token that sympy
  shattered into single-letter symbols.
- **Gap 21** (found testing gap 20's own fix, and worse): once a trig
  command becomes a real `cos(...)` call, a letter glued directly
  against it with no space (`d\cos\theta` -> `dcos(theta)`) made sympy
  drop the trig function entirely and shatter the whole expression into
  single letters multiplied together -- a silently wrong equation, not
  merely a lost warning.

Both fixed and regression-tested (48 tests total now) in the previous
commit, before any Grade 11 Physical Sciences seed data was written.
See `docs/REBUILD_SPEC.md` Section 1 and `docs/BUILD_LOG.md`'s 13 Nov
2026 entry for full technical detail.

## Implementation

- `seed_dev_data.py`: `_PHYSICAL_SCIENCES_GRADE11_TOPICS` /
  `_PHYSICAL_SCIENCES_GRADE11_QUESTIONS`, added to `SUBJECTS` as a
  fourth entry (after Grade 11 Pure Mathematics, so both Grade 10
  subjects it might cross-reference are already seeded).
- `SymbolKeyboard.jsx`: three new entries for the topic names with no
  Grade 10 namesake (Newton's Laws, Newton's Universal Law of
  Gravitation, Electromagnetism). The other three Grade 11 topics
  share an exact name with their Grade 10 counterpart, so
  `TOPIC_SYMBOLS` (keyed by name, not id) already covers them for
  free -- no change needed there.
- No backend/frontend changes beyond that were needed: `GET /subjects`
  and `SubjectPicker.jsx`'s grade-disambiguation (from the Grade 11
  Maths UI fix) already generalize to a fourth subject with no further
  changes.

## Consequences

- Not yet live-tested against a real Claude call, or run against a
  real Postgres instance at all -- handed to Siya, same handoff as
  every previous content expansion.
- Grade 12 (both Pure Mathematics and Physical Sciences) is the
  natural next step after Grade 11 is confirmed working on both
  subjects.
- The "inexact cross-grade mapping" pattern this ADR establishes
  (some topics get a direct cross-grade edge, some chain within-grade
  only, some are simply new) is likely the more common case going
  forward than Grade 11 Maths' unusually clean 1:1 mapping -- worth
  expecting, not treating as a special case, when Grade 12 is scoped.
