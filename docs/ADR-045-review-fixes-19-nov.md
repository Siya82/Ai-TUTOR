# ADR-045 — Fixes from the 19 Nov 2026 review

**Date:** 19 Nov 2026 · **Status:** Accepted

All 17 items in `docs/CODE_REVIEW_2026-11-19.md` were fixed, plus two problems
found while testing them. The decisions worth recording:

- **Unreleased tests stay hidden everywhere.** A single helper,
  `released_attempts_only()`, is the rule for any view that turns attempts
  into percentages. Use it in any new learner or family view.
- **Teacher overrides beat the AI.** If `attempts.marked_by_user_id` is set,
  `is_correct` is the teacher's decision. Completion, marks, CONNECT and
  INSIGHTS all read `is_correct`, so they follow automatically. A learner's
  new answer is AI-marked again.
- **Daily tutor limit:** per learner per South African day, default 60
  (`TUTOR_DAILY_LIMIT`, 0 = off). It's checked before any Claude call, so a
  refused question costs nothing.
- **Tokens:** still one hour, renewed every 30 min by the open app
  (`POST /auth/refresh`). `api.js` swaps the renewed token in, so screens
  don't re-render. A password change or deactivation still revokes at once
  (`token_version`).
- **Assignments, once issued, keep their questions and learners.** Use
  Duplicate to change them. Delete only before anyone has answered;
  otherwise Close, so learners' work and marks survive.
- **Audit trail:** one row per sensitive action, written in the same
  transaction as the action. It never stores passwords, codes or
  conversation text. Readable in ADMIN → Activity by management only.
- **Family logins follow the child:** deleting a learner removes parent or
  viewer logins with no other child, and keeps those who still have one.
- **Integration tests need their own database** (`TEST_DATABASE_URL`), so
  they never touch dev or production data. Without it they skip.
- **Throttles** (login, SMS codes, registrations, tutor limit) are in memory
  or in the database per request. The in-memory ones must move to the
  database or Redis before running more than one server (GCP plan).
