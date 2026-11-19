# ADR-048 — Fixes from the 19 Nov 2026 deep scan

**Date:** 20 Nov 2026 · **Status:** Accepted

Every code item in `docs/DEEP_SCAN_2026-11-19.md` (H1–H5, M1–M8, L1–L8) is
fixed. Three more problems turned up while fixing them and are fixed too
(marked *found*). The items that need people rather than code are listed at
the end: they are still open.

## Decisions worth recording

**Child safety (H1).** Every tutor prompt now has a fixed safeguarding block
straight after the identity line:
- stay on schoolwork, and never ask for personal details;
- on a disclosure of harm, respond kindly and give Childline 116 and police
  10111, and say to tell a trusted adult or teacher;
- textbook text and learner answers are fenced (`<<<REFERENCE … REFERENCE>>>`,
  `<<<STUDENT_ANSWER … STUDENT_ANSWER>>>`) and treated as data, never as
  instructions.

`tests/test_safeguarding_live.py` is a red-team set against the real model.
It's excluded by default (it costs money): `pytest -m live_api`. **THUTOra
never alerts anyone itself.** Schools need their own safeguarding process
(see "Needs people").

**Dependencies (H2).** Upgraded to versions with no known vulnerabilities:
- FastAPI 0.165, uvicorn 0.54, pypdf 7.1, python-multipart 0.0.34, vitest 5;
- **PyJWT replaces python-jose** (unmaintained). `auth.py` keeps the same
  `JWTError` name.

CI now runs `pip-audit` and `npm audit` and fails on findings.

**Connections during AI calls (H3).** `release_connection(db)` commits and
hands the connection back before every Claude call (tutor, marking,
translation). If the call fails, the tutor deletes the learner's message
and its attachments, so nothing is orphaned. Measured with 40 learners
asking at once and a 5 s AI delay:
- before: median 10.6 s, slowest 15.7 s;
- after: all under 5 s.

The pool is now 10 + 10 per instance. `docs/RUNBOOK.md` gives the Cloud SQL
connection budget.

**Production basics (H4).**
- The API **refuses to start** in production with:
  - a weak `JWT_SECRET_KEY`;
  - localhost or `http://` in `CORS_ORIGINS`;
  - `SMS_PROVIDER=console`;
  - no Anthropic key.
- `/docs` and `/openapi.json` are off in production.
- Every response gets security headers and `Cache-Control: no-store`, plus
  HSTS in production.
- `LOG_FORMAT=json` gives Cloud Logging severities and Error Reporting
  tracebacks. Frontend crashes are sent to `POST /client-errors`, which is
  rate-limited and keeps no page content.
- New files:
  - `backend/Dockerfile`;
  - `frontend/firebase.json` (CSP and headers);
  - `frontend/.env.production.example`;
  - `backup-thutora.ps1`;
  - `docs/RUNBOOK.md` (backups, restore drill, incidents).
- *Found:* the frontend had the API address hard-coded to
  `http://localhost:8000`, so no deployed build could have worked. It's now
  `VITE_API_BASE_URL`.
- *Found:* behind Cloud Run every request appears to come from Google's
  proxy, so the per-address limits would have locked out whole schools. The
  Dockerfile runs uvicorn with `--proxy-headers`.

**Cost control (H5, L7).**
- Every Claude call records its tokens and cost in `ai_usage`, per school,
  user and feature.
- A school can set a monthly AI budget (ADMIN → School settings). When it's
  used up:
  - the tutor says so (429);
  - marking falls back to "your teacher will mark this one";
  - translation falls back to English.
- `scripts/ai_costs.py` shows spend.
- `FALLBACK_MODEL` is tried once on overload or server errors.

**Consent (H5).** A school can switch on "require recorded consent". Then a
learner without a current consent record can't use the AI tutor (403, with a
clear message). Everything else still works.

**Retention (M1).** `python -m scripts.retention` (nightly; `--dry-run` to
count).
- Always clears:
  - rate-limit events older than 2 days;
  - SMS codes older than a day;
  - family invites more than 30 days spent.
- Conversations, loose uploads and the audit trail are deleted only after
  `RETENTION_*_DAYS`. The default 0 keeps them until periods are agreed.
- A conversation with a recent message is kept whole.

**Limits that survive restarts and more than one server (M2, M3, M4, L6).**
All throttles now live in the database (`rate_events`), not in memory:
- login: per device 5 per 15 min, per login 30 per hour, per address 300 per
  15 min, then a 15-minute lock;
- family invite redemption: 10 per address per hour, 50 per school per day;
- SMS codes and school registrations.

Uploads:
- 30 per learner per day;
- read in chunks with a size cap;
- content checked against the claimed type (magic bytes);
- PDFs capped at 40 pages and extracted in a thread with a 20 s timeout.

**Test integrity (M5).** While a learner has an open test, a tutor question
that matches one of its questions:
- gets an extra instruction (coach the idea with a different example, don't
  solve it);
- is tagged with the test.

The teacher's answer review shows how many test questions the learner asked
THUTOra about.

**Faster screens (M6).**
- Each product loads on demand: a learner never downloads TEACH, ADMIN,
  CONNECT, INSIGHTS or the PDF reader. LEARN's first load went from 345 KB
  to 220 KB gzipped.
- API responses over 1 KB are gzipped.
- Today sends at most 20 "needs help" rows and 20 quiet names, plus counts.

**Tests (M7).** New HTTP tests cover:
- classes, roles and allocations (granting and revoking access);
- notices and acknowledgement;
- Today scoping, dashboard scoping and INSIGHTS access;
- books, consent, SMS sign-up, viewer invites;
- retention, security headers, gzip and abuse limits.

Backend: 330 tests pass with no warnings. Frontend: 22.

**Question quality (M8).** Teachers can report a question from the answer
review. `scripts/question_reports.py` lists reports and can hide a question
(`questions.is_hidden`), which takes it out of the bank and out of
practice sets.

**Tidy-ups.**
- L1: the school picker is now a plain list of buttons, and axe is clean on
  every screen.
- L2: the translation cache keeps only today.
- L3: `video_resources` and `practicals` are documented as planned (ADR-005),
  not removed.
- L4: the Assignments tab moved to its own file; `TeacherAdminScreen.jsx`
  went from 1,351 to 550 lines.
- L5: Pydantic `ConfigDict`; FastAPI lifespan replaces `on_event`.
- L8: the duplicate index was dropped.

## Migration

`0022_deep_scan` adds:
- `rate_events`, `ai_usage`, `question_reports`;
- `questions.is_hidden`;
- `schools.require_consent` and `schools.ai_budget_usd_month`;
- `tutor_messages.test_assignment_id`.

It drops `ix_learners_user_id`. Upgrade and downgrade were both tested.

## Needs people (still open)

These need people, not code:
- **A safeguarding process with each school:** who reads a disclosure, and how
  fast.
- **A data-processing agreement with Anthropic.** This is also the place to
  confirm learner conversations aren't used for training.
- **Retention periods:** agree them with schools, then set
  `RETENTION_*_DAYS`.
- **A consent policy:** decide when to switch on "require recorded consent".
- **Teacher review** of the generated question bank.
- **isiZulu content for Grades 11–12** (ADR-021: never invented).
