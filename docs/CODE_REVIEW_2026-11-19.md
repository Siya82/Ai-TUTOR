# Code review — 19 Nov 2026 (after ADR-035 to ADR-044)

Whole-app pass after the SamarthX polish phases, brand work, parent
verification and ADMIN. Excludes items waiting on outside people (SMS
provider, SA-SAMS sample, designer files, privacy-notice legal review,
zero-rating, GCP).

## High

1. **Parents can see unreleased test results.** CONNECT's topic accuracy
   and weekly summary (`connect.py::_overview`) count every marked attempt,
   including answers to test-mode assignments whose results the teacher
   hasn't released. The work list hides them; the percentages don't.
2. **Teachers can't see answers or override AI marks.** The assignment
   detail shows counts per learner, not what each learner wrote, the AI's
   feedback, or a way to correct a wrong mark. AI marking with no teacher
   review is the biggest trust gap for schools.
3. **No limit on tutor use per learner.** `/tutor/message` has no daily
   cap. One learner (or a script with a learner's login) can run up the
   Claude bill without limit.
4. **No endpoint or permission tests in the repo.** All 267 backend tests
   are unit tests. The HTTP checks for scoping, parent/viewer isolation,
   INSIGHTS suppression, privacy and sign-up run only from scratch
   scripts outside the repo, so CI never runs them.

## Medium

5. **Chat is lost on refresh or after an hour.** The session id lives in
   memory; tokens expire after 60 minutes with no renewal; learners have no
   list of past conversations even though every message is stored.
6. **Learners have no "My progress".** Teachers and parents see a learner's
   strengths and weak topics; the learner doesn't.
7. **Assignments can't be changed.** No edit, extend due date, close early,
   duplicate or delete after creation.
8. **Can't correct a person's details.** No way to fix a learner's name,
   grade or student number, or a staff member's name, short of deleting
   and recreating the account (which loses history).
9. **No "change my password"** for anyone, except the forced first-login
   change.
10. **Privacy gaps.** Deleting a learner's data leaves their parent and
    viewer logins behind with no child (orphans). The POPIA data export
    omits guardian contacts and linked parents.
11. **No audit trail** for sensitive actions: password resets, account
    switch-off, role grants, consent changes, data export and deletion.
12. **Login school picker won't scale.** One drop-down of every school and
    office (a national roll-out means thousands), defaulting to the first
    entry (currently an office), with no search and no memory of the last
    school used on the device.

## Low

13. **Mobile:** TEACH and ADMIN tab bars push the page wider than the
    phone (390px screen → 600–820px page) instead of scrolling sideways.
14. **No error boundary:** a rendering error shows a blank page.
15. **Thin content:** about 1 content chunk and 2 bank questions per topic,
    and isiZulu Home Language exists for Grade 10 only. "Send practice"
    and assignments soon repeat questions.
16. **Registration requests are silent:** a new "Register your school"
    request appears only when someone runs the CLI. Nothing logs it
    prominently.
17. **Throttles live in memory** (login, SMS codes, registrations): fine on
    one server, ineffective once there are several. Revisit with GCP.

## Status — all fixed the same day (see ADR-045)

| # | Fix |
|---|-----|
| 1 | `services/attempt_visibility.py`: CONNECT and "My progress" leave out answers to unreleased tests. Regression test proves it. |
| 2 | Teachers see each learner's answers, the AI feedback and the model answer, and can mark right/wrong with a note (shown to the learner once results are visible). |
| 3 | `TUTOR_DAILY_LIMIT` (default 60 per South African day, 0 = no limit); friendly 429; "N questions left today" in LEARN. |
| 4 | `tests/integration/`: 20 HTTP tests through the real app and Postgres (scoping, parents/viewers, privacy, overrides, limits, profile switches). In CI via `TEST_DATABASE_URL`. |
| 5 | Each topic's conversation reloads from the server; logins renew every 30 min while the app is open. |
| 6 | LEARN → My progress (same numbers as the parent view). |
| 7 | Edit title/instructions/due date, close now / reopen, duplicate, delete (only before anyone answers). |
| 8 | ADMIN: edit a learner's name, student number or grade, and a staff member's name or number. |
| 9 | "Password" button in every product header. |
| 10 | Export now includes guardian contacts and family logins. Deleting a learner removes parent/viewer logins that have no other child. |
| 11 | `audit_events` table plus ADMIN → Activity. It records resets, switch-off, roles, consent, export/delete, mark changes, edits, settings, promotions and parent links. |
| 12 | Login page searches schools (name or EMIS) and remembers the last school on the device. |
| 13 | Tab bars scroll inside themselves on phones: the page is 390px wide at 390px. |
| 14 | Error boundary: "Something went wrong — Reload" instead of a blank page. |
| 15 | +105 Maths questions (3 per topic, Grades 10-12) and +40 physics questions (2 per topic). Numeric answers are re-computed in a test. isiZulu Grades 11-12 still need a fluent author (ADR-021: no invented isiZulu content). |
| 16 | A new registration logs a WARNING with the review command; start-up reports pending requests. |
| 17 | Documented: move the throttles to the database or Redis when there's more than one server (GCP plan). |

Also found and fixed while testing:
- When AI marking failed, the raw API error was shown to learners and teachers. It now shows a plain message and logs the error.
- With the textbook open, the new 4th tab and the Send button ran under the book panel. The chat column now shrinks and the view buttons become icons.
