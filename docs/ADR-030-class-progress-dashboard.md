# ADR-030: TEACH class progress dashboard

**Status:** Accepted
**Date:** 17 November 2026

## Context

ADR-024 put `/api/v1/dashboard/*` (overview, learner detail, mastery, risk)
behind teacher auth and school scoping, but deliberately wired none of it
into `TeacherAdminScreen.jsx`. ADR-028 then produced the first real `Attempt`
rows anywhere in the app (assignment answers), so the mastery/risk data
those endpoints read finally exists. Asked what to build next in TEACH,
Siya chose (via `AskUserQuestion`, "Recommended") a class progress
dashboard over classes/groups, the parked resources slot, or live-testing
ADR-029 first.

## Decision

A fifth **Progress** tab in `TeacherAdminScreen.jsx`
(`components/ProgressPanel.jsx`) with two views:

- **Class view:** grade filter chips; summary tiles (learners, active in
  the last 7 days, high/medium risk, not started, class accuracy); a
  learners table sorted riskiest first, with each learner's risk badge,
  accuracy, answers, last activity and the topics that need attention; and
  a topics table (CAPS order) with class accuracy and how many learners are
  struggling on each.
- **Learner view** (click a row): risk cards with ADR-004's own factors and
  suggested interventions, mastery by topic, and recent incorrect answers
  with their AI feedback.

Backed by one new endpoint, `GET /api/v1/dashboard/progress?grade=`
(teacher-only, own school only, same as every ADR-024 dashboard route),
plus the existing `GET /api/v1/dashboard/learners/{id}`.

### How risk is computed

The ADR-004 rules in `risk_assessment.py` are unchanged. What changed is
which topics they run on and how the data is fetched:

- **Candidate topics only:** topics the learner has attempted, plus topics
  whose direct prerequisite they have attempted (and that are at or below
  their grade). The prerequisite rule can legitimately flag a topic before
  the learner starts it, which is the point of an early warning. Topics with
  no evidence on either side are skipped, since they can only ever come
  back "low".
- **No N+1:** the old learner-detail path ran one or two queries per topic
  in the learner's grade. Both the class view and the learner view now run
  a fixed number of queries (learners, their scored attempts, all topics)
  and aggregate in memory in a new pure module,
  `app/services/class_progress.py`, which is unit-tested without a database.
- **No data is not low risk:** a learner with zero scored attempts gets
  `risk_level: null` and shows "No data yet", not "Low".
- **"Struggling" on a topic** means below 60% over at least 2 answers. The
  60% line is ADR-004's own `PREREQUISITE_MASTERY_THRESHOLD`, so the
  Progress tab and the risk model agree on what "weak" means.

### Bug fixed along the way

`dashboard.py`'s mastery and overview queries averaged
`Attempt.is_correct.cast(Float)`. PostgreSQL has no boolean-to-float cast
(confirmed: `cannot cast type boolean to double precision`), so both
endpoints would have returned a 500 as soon as any scored attempt existed.
It never surfaced because no `Attempt` row existed until ADR-028. Replaced
with `AVG(CASE WHEN is_correct THEN 1 ELSE 0 END)`.

## Consequences

- A teacher can now see, per school and per grade, who needs help and on
  what, using real assignment results.
- The prerequisite rule is generous: a learner weak on one foundational
  topic (say Algebraic Expressions) gets a medium flag on every topic that
  builds on it. That's how ADR-004 was designed. If it reads as noise once
  real classes use it, the fix belongs in the risk model (for example a
  minimum attempt count before a prerequisite counts as weak), not in the UI.
- Accuracy counts every scored attempt, resubmissions included. This is
  practice history, which is a different measure from an assignment's
  "latest answer counts" score (ADR-029).
- `risk.py` vs `risk_assessment.py` consolidation (flagged since August) is
  moot here: only `risk_assessment.py` exists in the rebuilt repo.

## Verification

First feature on this project verified against a **real PostgreSQL + pgvector
database** in the sandbox, not only `ast.parse` or pure unit tests: migrations
0001–0007 applied, `seed_dev_data.py` run, synthetic students and attempts
written, and every dashboard endpoint called through the real FastAPI app with
a real teacher JWT (a student token correctly gets 403). Full backend pytest
suite on Python 3.12: **175 passed** (including the three files previously
blocked by the sandbox's Python 3.10). `vite build` clean, `eslint` clean on
the new component, and both views rendered in headless Chrome against that
backend.

## Not done

- Not live-tested on Siya's machine.
- No per-class view (no classes/groups yet), no export, no time-range filter.
- Assignments per learner are not shown in the learner view yet. The
  Assignments tab still holds per-assignment completion.
