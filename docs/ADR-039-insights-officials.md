# ADR-039: INSIGHTS — circuit and district dashboards

**Date:** 19 Nov 2026 · **Status:** Accepted

## Decision
- **Structure:** `districts` → `circuits` → schools (`schools.circuit_id`),
  migration 0017. Officials are users with role `official` belonging to an
  **office** (a `schools` row with `kind='office'`, so they log in by picking
  "<Name> District/Circuit Office" on the normal login screen). Each official
  has an `official_assignments` row for one district or one circuit.
- **Set-up is outside the app** (it follows an agreement with the department):
  `python -m scripts.manage_insights add-district | add-circuit |
  assign-school | add-official | list`.
- **Dashboard (last 30 days):** area totals (schools, learners, participation,
  accuracy); every school with participation and a Good (≥70%) / Watch
  (50–69%) / Concern (<50%) band; weakest topics across schools; circuit
  filter for district officials; drill-down per school by grade×subject,
  weakest topics and classes.
- **Privacy:** aggregates only — no learner names or answers ever reach an
  official — and any group with fewer than 5 learners is shown as "Too few
  learners".

## Later
Province-level officials, trends over terms, and exporting a circuit report.
