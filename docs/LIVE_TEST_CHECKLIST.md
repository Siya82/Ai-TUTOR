# THUTOra — Live Test Checklist

Consolidated, in priority order, from everything flagged as "not yet live-tested" or "needs confirming on your machine" across ADR-022 through ADR-028 and their matching `BUILD_LOG.md` entries. Nothing here is new code — every item below is already built and committed; this is just confirming it against the real Claude API, your real browser, and your real Postgres instance, per this project's own "ship then verify" rule.

**One-time catch-up before anything below:** `git pull`, `pip install -r requirements.txt` (or run `start-thutora.ps1`), `alembic upgrade head` (picks up migrations 0004–0006), then `python -m scripts.seed_dev_data` to re-seed and backfill.

## Priority 1 — Assignments end-to-end (ADR-028)

This is the highest-stakes item: it's the first code path in the whole app that actually writes an `Attempt` row, so it's also the first real test of whatever the mastery/pace/risk logic does with genuine data.

- [ ] Log in as the dev teacher (`T00001` / `DevPass123!`)
- [ ] Author a custom question in the Assignments tab
- [ ] Create an assignment, target the dev student (`100001`)
- [ ] Log out, log in as the dev student, open Assignments, answer the question
- [ ] Confirm AI feedback comes back for a correct answer (marked correct)
- [ ] Submit a deliberately wrong answer on a second question — confirm it's marked incorrect, not silently passed
- [ ] Check the dashboard / roster mastery view for that student afterward — first time it should ever show real, non-empty attempt data
- [ ] Note anything that looks off in the AI-marking *judgment* itself (the defensive JSON parsing is unit-tested; marking quality against a real answer isn't)

## Priority 2 — ADR-024 teacher dashboard walkthrough

Interrupted last time by the stale-password bug, which is now fixed.

- [ ] Roster tab shows the existing dev student
- [ ] Add a new student via the admin UI; confirm the one-time temp-password display
- [ ] Log out, log in as that new student, confirm the forced password-change-on-first-login step

## Priority 3 — Grade 11/12 content batch (ADR-022, ADR-023)

- [ ] Ask a Grade 12 Pure Mathematics question — try Differential Calculus specifically, the flagged highest-risk new notation
- [ ] Ask a Grade 12 Physical Sciences question
- [ ] Ask a Grade 12 Accounting question
- [ ] Ask an English Home Language Grade 11 question, then a Grade 12 question

## Priority 4 — Grade-scoped visibility (ADR-026)

- [ ] Log in as a real Grade 10 student; confirm the sidebar hides Grade 11/12 subjects
- [ ] POST `/tutor/message` directly with a higher-grade `topic_id`; confirm it 403s
- [ ] Confirm the dev/admin account (grade widened to 12) still sees every grade

## Priority 5 — Dev/admin diagnosis bypass (ADR-027)

- [ ] Run `pytest tests/test_tutor_orchestration.py -v` on your machine (blocked in the cloud sandbox by Python 3.10 vs. `datetime.UTC`)
- [ ] Log in as the dev account, ask a Grade 12 question cold (no prior attempts); confirm it teaches Grade 12 directly with no diagnosis-note redirect

## Priority 6 — Diagnosis redirect names the grade level

- [ ] Trigger a real redirect on a real (non-bypassed) student — ask something whose prerequisite chain goes back a grade — and confirm Claude's reply actually states the grade(s) involved, not just the topic names

## Priority 7 — MathGuard gap 23 (boxed answers, prime notation, limits)

- [ ] Re-ask the Grade 12 first-principles differentiation question from your original screenshot; confirm `\boxed{}` unwraps and the badge no longer gets stuck on "partially checked" for the same reason as before
- [ ] Pose a standalone "evaluate this limit" problem with a deliberately wrong answer; confirm MathGuard actually catches it

## Known accepted gaps (context while testing, not test items)

- No endpoint yet to browse/reuse the seeded CAPS question bank inside an assignment — custom-authored questions only
- No class/group targeting or due-date enforcement on assignments yet
- No formal "tests" type or dedicated TEACH progress dashboard yet
- `backend/debug_login_check.py` is an untracked scratch file from the login debugging session — safe to delete, was never committed

**Parked, not a test item:** the teacher/learner "resources" slot discussed today (topic-scoped, textbook-agnostic curated links/documents). Decide the schema when it's next prioritized — no code written yet.

---
Compiled 15 Nov 2026, consolidating open items from ADR-022 through ADR-028 and their `BUILD_LOG.md` entries.
