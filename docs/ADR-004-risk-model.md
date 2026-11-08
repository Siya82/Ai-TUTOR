# ADR-004: Early-Warning Risk Model — Rule-Based v1, Not Trained ML

**Status:** Accepted
**Date:** 2026-07-31

## Context

The goal is to identify learners likely to fail *months before it happens*,
not just report that they already have. This is a genuinely high-value
capability for education departments — but it needs to be built honestly.

## Decision

**v1 (this pilot) is rule-based and interpretable, not a trained model.**

A trained predictive model (the kind that could plausibly forecast failure
months out with real statistical confidence) needs a substantial dataset
of historical learner trajectories with known outcomes — the pilot will
not have that in month one, or realistically in year one. Building a model
and presenting its output as "predictive" before it has real data behind
it would be misleading, especially in a context (education, at-risk
learners) where a wrong or opaque flag on a child has real consequences.

Instead, v1 combines three interpretable, individually-justifiable signals
into a risk level:

1. **Declining accuracy trend** — this week vs. last week on a topic.
2. **Weak prerequisite mastery** — a learner starting a new topic with
   shaky mastery of what it depends on is a leading indicator, not a
   lagging one: it can flag risk on the new topic *before* the learner
   has struggled on it directly, which is the actual "months before it
   happens" mechanism available honestly at this stage.
3. **Disengagement** — inactivity following a prior pattern of engagement.

Each flag comes with a plain-language reason and a concrete recommended
intervention, not just a score — this matters for teacher/department
trust and for the model being auditable/contestable.

## Consequences

- Every risk flag is explainable in one sentence to a teacher or parent —
  a deliberate constraint, since an opaque risk score on a learner without
  a stated reason is not something a school should act on.
- This system is also the pilot's data-generation phase: pilot outcomes
  (which flagged learners did/didn't improve, which interventions helped)
  become the labelled training data a genuine predictive model would need.
  The honest pitch to a funder is "this becomes a trained model once we
  have a term of real outcomes," not "this already is one."
- Thresholds (accuracy drop %, inactivity days, prerequisite mastery
  cutoff) are initial estimates, not calibrated against real outcomes yet
  — expect to tune these once pilot data exists.
