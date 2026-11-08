# ADR-006: Narrow Pilot Scope to Grade 10 Mathematics Only

**Status:** Accepted
**Date:** 2026-07-31
**Supersedes (partially):** the two-subject scope in the original MVP roadmap and ADR-001

## Context

The original pilot scope was Grade 10 Pure Mathematics + Physical Science,
justified by content overlap between the two subjects. A later strategy
document (the "Zynora" proposal) argued for a stronger, different bet:
solve one subject exceptionally well before expanding, on the reasoning
that Grade 10 Maths is the specific transition point where learners move
from arithmetic to abstraction, and is a prerequisite for success not just
in Grade 11/12 Maths but in Physical Sciences, Engineering, Computer
Science, Data Science, and Economics — so a genuinely excellent Grade 10
Maths tutor has outsized leverage even for learners' other subjects.

## Decision

Narrow the pilot to **Grade 10 Mathematics only**. Depth over breadth: a
tutor that handles one subject's full concept graph with real rigor
(diagnosis, personalization, mastery tracking) is a stronger v1 than two
subjects handled more shallowly.

## What happens to the Physical Science work already built

Not discarded — paused. `ADR-005`'s labs architecture (deterministic
calculation engine, `Practical`/`PracticalRun` schema, the verified Mg+HCl
practical) and the `VideoResource` model are subject-agnostic in design;
they were built as reusable patterns, not Physical-Science-specific code.
Re-enabling Physical Science later is a scope decision, not a rebuild.

## Consequences

- Content ingestion (Step 1 of the original roadmap) now needs only one
  subject's CAPS syllabus + past papers — meaningfully less curation work
  before the tutor can be grounded.
- The `Subject`/`Topic` schema already supports multiple subjects per
  grade, so this is a scope/prioritization decision, not a schema change.
- Every future ADR and build log entry should be read as Maths-first;
  Physical Science entries above this point in the log remain accurate
  history, not current scope.
