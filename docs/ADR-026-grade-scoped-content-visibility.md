# ADR-026: Grade-scoped subject/topic visibility and access

**Status:** Accepted
**Date:** 15 November 2026

## Context

While live-testing the just-shipped grade-context diagnosis redirect (a small enough change to be captured via BUILD_LOG only, not its own ADR), Siya raised a related but separate concern: `GET /subjects` and `GET /topics` have never filtered by grade at all, and never required authentication -- both endpoints have carried the documented caveat "No auth yet" since 12 Nov 2026 (ADR-013) and 8 Nov 2026 respectively. In practice this means the subject/topic sidebar (`SubjectTopicSidebar.jsx`) currently shows a Grade 10 student every subject at every seeded grade, including Grade 11 and Grade 12 -- a student can browse into, and manually select, content well ahead of where they actually are. Siya's explicit requirement once THUTOra is live: a student should only be able to see their own grade's subjects/topics and the grades below it, never a grade ahead.

## Decision

**`GET /subjects` and `GET /topics` now require a logged-in learner and filter to `Subject.grade <= learner.grade`.** Both endpoints gained a `learner: Learner = Depends(get_current_learner)` dependency (the same one `tutor.py`/`attachments.py` already use) and a `.where(Subject.grade <= learner.grade)` clause -- `/topics` needs a join to `Subject` to get there, since `Topic` itself has no grade column. The learner's grade is read from their own `Learner` row, resolved server-side from the bearer token -- there is deliberately no way for a request to ask for a different grade's content, the same posture ADR-017 already established for `learner_id` itself (never client-supplied, always resolved from the token).

**`POST /tutor/message` gained the actual enforcement point, not just the picker.** Hiding a topic from `/subjects`/`/topics` only changes what the UI shows; a `topic_id` for a Grade 12 subject is still a real UUID a client could POST directly. `send_tutor_message()` now checks `requested_topic.subject.grade > learner.grade` immediately after resolving the topic (right next to the existing 404-if-missing check) and returns 403, not 404 -- the topic is real, the learner just isn't allowed to be taught it yet. Without this, grade-scoping would have been a cosmetic UI restriction only, not a real one -- the same "the picker isn't the boundary" lesson ADR-024 already applied to the teacher dashboard (school-scoping the API, not just the UI).

**The frontend change is minimal by design.** `api.js`'s `fetchSubjects()`/`fetchTopics()` now take and forward a `token` (they previously called `getJson()` with none at all, even though the student is always logged in by the time `ChatScreen` mounts); `ChatScreen.jsx` passes `auth.token`, already available as a prop since ADR-017. No change to `SubjectTopicSidebar.jsx` itself -- it already just renders whatever subjects/topics it's handed, so a shorter, grade-filtered list from the backend is all that's needed to shrink what the student sees.

## Consequences

- `backend/app/routers/subjects.py`: `list_subjects()` now takes `learner: Learner = Depends(get_current_learner)` and filters by grade.
- `backend/app/routers/topics.py`: `list_topics()` same change, via a join to `Subject`.
- `backend/app/routers/tutor.py`: `send_tutor_message()` gained the 403 grade guard described above.
- `frontend/src/api.js`: `fetchSubjects(token)`/`fetchTopics(token)` now take and forward a token.
- `frontend/src/components/ChatScreen.jsx`: passes `auth.token` to both calls; the loading effect's dependency array now includes `auth.token`.
- Verified with `ast.parse` on all three backend files (same sandbox limitation as every prior change -- no `pgvector`/`pydantic_settings` env here to actually run the app) and `esbuild` bundling both edited frontend files (clean). No existing test file covers either router (`test_subjects.py`/`test_topics.py` don't exist), so nothing needed updating there, though their absence is itself worth naming -- see below.

## Open items (explicitly not done, not silently dropped)

- **No new test coverage added for this change.** Neither `subjects.py` nor `topics.py` had any existing tests to extend, and this sandbox can't run a real DB-backed pytest session to write new ones against (same `pgvector`/`pydantic_settings` gap as always) -- a real regression test for the grade filter (seed two grades, log in as the lower one, assert the higher one never appears) is a genuine gap, not assumed covered.
- **Not live-tested against a real Claude/browser session yet** -- handed to Siya next: log in as the dev student (Grade 10 per `seed_dev_data.py`) and confirm the sidebar no longer shows Grade 11/12 subjects at all, then confirm a direct `POST /tutor/message` with a Grade 11/12 `topic_id` now 403s.
- **Teacher/admin flows are untouched and don't need this** -- `TeacherAdminScreen.jsx` doesn't call `/subjects` or `/topics` at all, confirmed by reading the code, so nothing here affects a teacher's ability to see or manage a roster across grades.
- **A Grade 12 learner can still see Grade 10/11 content, by design** -- Siya's own stated requirement is "their own grade and the ones before," not "only their own grade," since the diagnosis engine's redirects (ADR-007, and the grade-context fix just shipped) legitimately need to teach a lower-grade prerequisite. This ADR does not change that; it only removes visibility/access to grades *ahead*.
