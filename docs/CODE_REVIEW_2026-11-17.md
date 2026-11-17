# THUTOra code review — 17 Nov 2026

A full pass over the backend (routers, services, models, scripts) and the
frontend, plus the automated checks. GCP deployment (ADR-033) is on hold.

> **Status (same day): items 1–19 are fixed** (commits 84c6203, 493f49b,
> aefcc9a and the follow-up). Two things remain, both outside the code:
> the POPIA work below, and `python-jose`, which stays because PyJWT can't
> be installed on the dev laptop while pip is blocked. The picomatch ReDoS
> advisory in `npm audit` is in the Vite build tooling only (never shipped
> to the browser) and has no patched version yet.

**Automated checks:** 220 backend tests pass; `vite build` clean; eslint has 7
errors (all "setState inside an effect") and 1 unused variable; pyflakes finds
5 unused imports; `npm audit` reports 4 low-severity advisories (an old KaTeX
pulled in by the markdown maths plugins).

Findings marked **(confirmed)** were reproduced against the running app.

## High — fix before any real learners use it

1. **Every learner in every school is visible without logging in (confirmed).**
   `GET /learners/` (app/routers/learners.py) has no auth and returns every
   learner's id, name and grade across all schools. It's a leftover from
   before login existed and the frontend no longer calls it.
   *Fix:* delete the route, its router registration and `fetchLearners()`.

2. **Test results can be improved after release.** A student can re-submit an
   answer at any time, and the latest attempt counts. After the teacher
   releases a test, the student sees the feedback, can re-submit, and the new
   mark replaces the old one. Due dates are also never enforced.
   *Fix:* refuse answers to a test once results are released; decide whether
   answers after `due_at` are refused or just flagged late.

3. **Phone photos over 5 MB will break the tutor.** Uploads are accepted up
   to 20 MB, but Claude rejects images over 5 MB, so the tutor turn fails with
   a 500. Many phone photos are 3–8 MB.
   *Fix:* shrink images in the browser before upload (canvas; no new package).

4. **Tutor chat history grows forever.** There's one session per learner per
   topic, and the whole history is sent to Claude on every turn. Cost rises
   with every message, and a long-used topic will eventually exceed the model's
   context and fail.
   *Fix:* send only the last N turns (e.g. 20), optionally with a short summary.

5. **The dev seed script has no production guard.** `seed_dev_data.py` creates
   a principal, teacher and students with the password `DevPass123!`. Run by
   mistake against a real database, that's a working back door.
   *Fix:* refuse to run unless `ENVIRONMENT=development`. (Needed before GCP.)

## Medium

6. **No protection against password guessing.** `/auth/login` has no rate
   limit or lockout, and student numbers are guessable. Tokens also stay
   valid for up to 60 minutes after a password change.
7. **"Must change password" is only enforced in the browser.** A user with a
   temporary password can call every API without changing it.
8. **A teacher can use another teacher's private question.** The question
   bank hides other teachers' questions, but `create_assignment` accepts any
   question id, and the assignment view then shows its text and model answer.
   *Fix:* only allow bank questions or the teacher's own.
9. **No length limits** on tutor messages, assignment answers or custom
   questions. A very long paste goes straight to Claude (cost, slow replies).
10. **AI failures and logging.** If Claude errors or times out, the tutor and
    answer marking return a bare 500 and the student's typed answer is lost
    on screen. There are no log statements anywhere in the backend, so
    live-test problems can't be traced afterwards.
11. **No database indexes on foreign keys.** None of the 41 foreign keys are
    indexed (Postgres doesn't do it automatically). Fine for a pilot; queries
    like "this learner's attempts" will slow down as data grows.
12. **Principals and HoDs can't see other teachers' assignments.** Assignment
    lists and details are limited to the teacher who created them, which
    doesn't match the school hierarchy (ADR-031).
13. **Missing school-admin functions:**
    - reset a forgotten password (today nobody can);
    - deactivate a learner or staff member who leaves;
    - move learners up a grade at year end;
    - rename or delete a class.

## Low

14. **Session expiry handling.** Sessions end after 60 minutes with no
    refresh. The chat, Progress and Assignments screens log out cleanly on
    expiry, but School, Library and the teacher Students tab just show an
    error.
15. **A malformed id in an assignment URL returns 500 instead of 404
    (confirmed).** Path ids are typed `str` instead of `uuid.UUID`.
16. **Slow-query patterns (N+1).** The student's assignment list recomputes
    the whole class's completion for every assignment; the teacher list runs
    two queries per assignment.
17. **Ageing dependencies.**
    - `python-jose` and `passlib` are no longer maintained (PyJWT and direct
      `bcrypt` are the usual replacements);
    - `datetime.utcnow()` is deprecated;
    - the low-severity KaTeX advisory;
    - the unused imports and lint errors above.
18. **No CI and no frontend tests.** Tests only run when someone remembers to.
19. **Duplicate whole-grade allocations aren't blocked by the database.** The
    unique constraint on allocations doesn't stop two whole-grade rows, because
    Postgres treats NULLs as distinct. The app's own check covers it today.

## Not code, but missing

- **POPIA:** the learners are minors. There is nothing yet for parental
  consent, a privacy notice, data retention, or deleting or exporting a
  learner's data. Learner messages and photos are also sent to Anthropic,
  which belongs in the privacy notice.
- **Backups and monitoring** for the database. Part of the GCP plan, but on
  hold with it.
