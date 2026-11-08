# ADR-007: Recursive Root-Cause Diagnosis

**Status:** Accepted
**Date:** 2026-07-31

## Context

The existing diagnostic (Step 3 of the original roadmap, `assess_risk` in
ADR-004) evaluates mastery *at* a topic. It does not answer a different,
more useful question: when a learner says "I don't understand quadratic
equations," is quadratic equations actually where the gap is — or is it
factorisation, or multiplication, or negative numbers, three steps back
in the prerequisite chain?

Teaching quadratic equations to a learner who hasn't mastered
factorisation wastes both the learner's time and the explanation's
usefulness — they'll hit the same wall for a different reason.

## Decision

Add `diagnose_root_gap()`: given a topic a learner is struggling with, walk
backward through the `Topic.prerequisite_id` chain checking mastery at
each step, and identify the *deepest* topic with insufficient (or
unconfirmed) mastery. That topic — not the originally requested one — is
where the tutor should start teaching.

Key design choices:
- **Unconfirmed mastery (too few attempts, or none) is treated as a
  possible gap, not a pass.** A prerequisite the learner has never been
  tested on is a real risk, and assuming competence there would defeat
  the point of root-cause diagnosis.
- **Stops at the first topic with confirmed solid mastery**, walking no
  further back than necessary — this keeps the diagnosis fast and avoids
  re-teaching things the learner already knows.
- **Fully traceable**: the diagnosis returns a human-readable reasoning
  trace (which topics were checked, why each was judged sufficient or
  not), not just a final answer — consistent with the project's
  "explainable, not a black box" principle (ADR-004) applied here too.

## Consequences

- Requires the prerequisite chain to be resolved (via repeated
  `Topic.prerequisite_id` lookups or a recursive query) before calling
  this — the function itself takes an already-ordered chain rather than
  querying the database, keeping it pure and testable, consistent with
  the pattern used in `personalization.py` and `risk.py`.
- This is where the Knowledge Graph concept from the Zynora document
  becomes real: not a separate graph database, just prerequisite chains
  in the existing `Topic` table, walked with real diagnostic logic.
- Depends on having enough `Attempt` history to be useful — for a
  brand-new learner with no history anywhere in the chain, this will
  walk all the way to the root topic, which is the conservative, correct
  behaviour but should be paired with a fast initial placement diagnostic
  so learners aren't always walked all the way back on day one.
