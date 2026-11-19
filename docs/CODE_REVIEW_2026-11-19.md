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
