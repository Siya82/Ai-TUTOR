# ADR-014: Grade 11 Pure Mathematics added -- deepen the proven subject, cross-grade prerequisite linking

**Status:** Accepted
**Date:** 2026-11-13

## Context

After the Physical Sciences addition (ADR-013) was live-tested, Siya
asked what should come next. Two live options existed: widen again
(another subject) or deepen (Grade 11/12 of the one subject MathGuard
already fully protects). Given ADR-013's own stated boundary --
Chemistry, Life Sciences, and Accounting were all deferred specifically
because most of their content isn't equation-shaped, so MathGuard can't
verify it the way it verifies Maths and Physics -- widening again would
either revisit that boundary or require picking a subject that still
fits it. Siya chose to deepen: Grade 11 (then Grade 12) Pure
Mathematics, matching REBUILD_SPEC.md's own originally-stated expansion
order before ADR-013 reversed it (subjects-before-grades), now resumed.

## Decision

Add **Pure Mathematics, Grade 11** as a third `Subject` row (same
`name`, different `grade` -- the schema's `UniqueConstraint("name",
"grade")` already supports this, no migration needed). 11 topics,
sourced from the DBE CAPS FET Mathematics Grades 10-12 document,
Section 3.2 (Grade 11 Annual Teaching Plan): Exponents and Surds,
Equations and Inequalities, Number Patterns, Functions, Analytical
Geometry (lines only -- the circle equation is Grade 12), Trigonometry
(reduction formulae, general solutions), Euclidean Geometry (circle
theorems), Measurement, Finance/Growth and Decay, Probability,
Statistics. Grade 12 is explicitly **not** included in this pass --
same "one slice at a time, live-test before the next one" discipline
already used for Physical Sciences.

Every Grade 11 topic maps 1:1 by name to its Grade 10 counterpart --
the cleanest possible cross-grade relationship found so far (unlike
Physical Sciences, which had no equivalent Grade 10 subject to map
onto at all).

### Cross-grade prerequisites

This is the one genuinely new design decision this ADR makes, not just
content: `Topic.prerequisite_id` is a single self-referential FK --
one parent per topic, not a DAG. Grade 10's own topics already use
this to chain within-grade (e.g. Trigonometry -> Equations and
Inequalities -> Algebraic Expressions). Grade 11 could have been
chained the same way, within-grade only, with no link back to Grade 10
at all -- simpler, but it would quietly throw away the exact thing this
expansion is supposed to demonstrate: ADR-011's root-cause diagnosis
differentiator working *across* grades, not just within one.

Chosen instead: **within-grade CAPS teaching order where CAPS actually
defines one, and a direct cross-grade prerequisite for every topic that
doesn't** (Exponents and Surds -> Grade 10 Exponents; Euclidean
Geometry -> Grade 10 Euclidean Geometry; Probability -> Grade 10
Probability -- the three Grade 11 topics with no natural *within-grade*
predecessor). Every other Grade 11 topic still reaches Grade 10
eventually, by walking its own within-grade chain back to one of those
three anchors -- not a direct one-hop link for all eleven, but real
cross-grade diagnosis without a schema change (a true multi-parent
prerequisite DAG) that a single-subject expansion doesn't yet justify.

`seed_dev_data.py`'s topic-tuple prerequisite field now accepts either
a plain string (same-subject, same as before) or a `(subject_name,
grade, topic_name)` tuple (an explicit cross-subject/cross-grade
reference). `_seed_subject` and `main()` thread a running
`all_seeded_topics` registry (keyed by `(subject_name, grade)`) through
the seeding loop so a later subject can resolve a reference into an
earlier one -- which makes **`SUBJECTS` list order load-bearing** for
the first time: Grade 10 Pure Mathematics must be seeded before Grade
11 Pure Mathematics references it. `_validate_subject_data` now checks
a cross-reference against the set of subjects already seen earlier in
`SUBJECTS`, so a wrong-order or typo'd reference fails fast at
validation time, before any DB write.

## Parsing gaps found (before any live test, this time)

Unlike Physical Sciences, where the four parsing gaps surfaced via a
live `/tutor/message` call, this round's CAPS research flagged two
likely notational gaps *before* any seed data was written, and both
were confirmed real in a sandbox before Grade 11 content was added at
all -- the project's "find it before it reaches a live reply"
discipline applied one step earlier than usual. See
`docs/REBUILD_SPEC.md` Section 1 and `docs/BUILD_LOG.md`'s 13 Nov 2026
entry for full technical detail:

- **Gap 18:** `\sqrt[n]{}` (nth-root surds, needed for Exponents and
  Surds) normalized to literal unparseable garbage.
- **Gap 19:** a compound/union inequality answer (`x < -2` or `x > 3`,
  the natural shape for a quadratic inequality) raised a raw, uncaught
  `TypeError` out of `verify_tutor_response` -- a genuine crash risk
  for the live endpoint, not just a lost warning. Fixed at the root
  (`split_relation` now rejects a malformed split) and again with
  `try`/`except` around every sympy call inside `verify_tutor_response`
  itself, so MathGuard can never take down the tutoring reply it sits
  beside, for this or any future not-yet-seen parsing edge case.

Compound/union inequality answers and trig general solutions (`theta =
30 + k*360`) are now known, accepted "left unverified" cases -- the
same category multi-symbol identities and Euclidean Geometry proofs
already are, not something this ADR claims to fully verify.

## Consequences

- Grade 11 has **not** yet been live-tested against a real Claude call
  -- same next step as every previous content expansion (seed, pytest,
  then a live `/tutor/message` smoke test).
- Grade 12 Pure Mathematics is the next natural step after Grade 11 is
  live-tested, not bundled into this pass.
- The cross-grade prerequisite mechanism this ADR introduces is
  reusable for Grade 12 (-> Grade 11) and, if Physical Sciences is ever
  extended to Grade 11, for that too -- it's a general capability now,
  not a one-off.
- `diagnosis.py`'s recursive prerequisite walk was not changed at all
  for this -- it already walks `Topic.prerequisite_id` generically,
  with no assumption that a prerequisite shares its topic's subject or
  grade, so cross-grade chains work through it for free.
