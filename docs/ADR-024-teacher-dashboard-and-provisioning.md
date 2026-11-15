# ADR-024: Teacher role -- dashboard auth gate and bulk student provisioning UI

**Status:** Accepted
**Date:** 15 November 2026

## Context

Two gaps have sat open in this project's own report and BUILD_LOG since the very first report (26 Aug 2026) and since ADR-017 (14 Nov 2026) respectively:

1. `/api/v1/dashboard/*` -- the teacher dashboard API (learner overview, mastery, risk) -- had no authentication at all. Anyone with the base URL could list every learner in the database.
2. There was no way to add a student except by re-running `scripts/seed_dev_data.py` directly on the machine running the backend. `app/services/auth.py`'s `provision_student()` existed and worked, but nothing outside a dev script could call it.

With the Grade 11/12 content scale-up (ADR-022, ADR-023) just finished and handed to Siya for live testing, he chose this as the next priority over resuming isiZulu work or a new subject (via `AskUserQuestion`): close these two platform gaps, scoped specifically as teacher-only dashboard access (no parent/admin tier yet -- ADR-017's own `User.role` design already anticipated adding roles later without a migration) and a **full admin UI**, not just a bare endpoint, for provisioning -- built as one combined step rather than two separate passes.

## Decision

**Teacher accounts reuse the exact same `User`/login mechanism ADR-017 built for students**, with `role="teacher"` instead of `role="student"`, and no `Learner` row at all (a teacher has no pedagogical profile). `User.student_number` is reused as a generic login identifier for a teacher's staff number rather than adding a new column -- naming it `staff_number` at the call-site (`provision_teacher()`'s own parameter) while the underlying column stays `student_number`, since this is structurally the exact same login mechanism with a different role, not a different shape that would justify its own column and migration. The same collision-checked number-generation loop `provision_student()` already had was extracted into a shared `_generate_unique_login_number()` helper so both functions get identical behaviour from one place rather than a second copy of the loop.

**There is still no self-service way to create a school's first teacher account.** ADR-017's "no self-service signup" stance (made on POPIA and scalability grounds for students) applies here too, maybe more so: `scripts/seed_dev_data.py` now also provisions a dev teacher account (idempotent, printed at the end of a run, mirroring the existing dev student account), but a real new school's first teacher is still something only this script -- or a future onboarding flow, not built here -- can create.

**Login and session re-hydration are now role-aware.** `LoginResponse`/`MeResponse` gained a `role` field, and `learner` became optional (`None` for a teacher) rather than required -- `login()` and `read_me()` in `app/routers/auth.py` branch on `user.role` instead of unconditionally resolving a `Learner` (which would 404 for every teacher). The frontend's `App.jsx` renders `TeacherAdminScreen` instead of `ChatScreen` based on that same `role` field, using the identical login screen for both roles (school + student/staff number + password) -- the backend's response is what decides which screen comes next, not anything the login form itself needs to know.

**Dashboard endpoints are now gated by a new `get_current_teacher` dependency** (403, not 401, for a valid token carrying the wrong role -- the token itself isn't invalid, the role just isn't allowed here), and -- going a reasonable step beyond "just add auth" -- **every dashboard endpoint is now scoped to the authenticated teacher's own school.** The overview list filters by `school_id` via a join through `User`; every learner-scoped endpoint (`detail`, `mastery`, `risk`) calls a new `_assert_same_school` check before returning anything, so a teacher at School A gets an honest 404 (not real data, and not a different error that would leak that the learner exists elsewhere) for a `learner_id` that belongs to School B. This wasn't explicitly asked for in those exact words, but it's the natural, expected consequence of "teacher-only" once there's more than one school in the picture at all -- flagged here explicitly rather than silently bundled in. One side effect worth naming: a `Learner` seeded without a linked `User` (old dev data from before ADR-017) has no school to scope it to, so it no longer appears in any dashboard view at all -- treated the same as "not this teacher's," a 404, not a crash.

**Bulk provisioning splits pure CSV parsing from the DB-touching provisioning loop**, the same split this project uses everywhere a service does both (e.g. `app/services/attachments.py`). `parse_student_csv()` (in the new `app/services/admin.py`) takes raw CSV text and returns parsed rows plus per-row errors -- no DB, unit-tested directly. `bulk_provision_students()` then loops over already-parsed rows calling `provision_student()`, catching a per-row failure (most likely a collision on a caller-supplied `student_number`) without aborting rows already created earlier in the same upload -- a teacher uploading 30 students shouldn't lose all 30 because row 17 has a typo.

**The admin UI is a full page, not a bare endpoint**, per Siya's explicit choice: `TeacherAdminScreen.jsx` has three tabs -- a roster table (`GET /admin/students`), a single-student form (`POST /admin/students`), and a CSV bulk-upload form (`POST /admin/students/bulk`) -- reusing `ChatScreen`'s existing header classes (brand, profile, logout) for visual consistency rather than building a second header from scratch. Every newly-created student's temp password is shown exactly once, directly in the result card, matching `provision_student()`'s own "this is the only point the plaintext password exists outside the student's own head" posture from ADR-017 -- there is deliberately no way to retrieve a temp password a second time.

## Consequences

- `app/services/auth.py`: `provision_teacher()` added; `_generate_unique_login_number()` extracted and shared with `provision_student()`. No schema/migration change -- `User.role` was already a plain string per ADR-017's own design.
- `app/core/security.py`: `get_current_teacher()` added.
- `app/schemas/auth.py` / `app/routers/auth.py`: `role` field added to both response schemas; `learner` made optional; `login()`/`read_me()` branch on role.
- `app/routers/dashboard.py` / `app/services/dashboard.py`: every endpoint now requires `get_current_teacher`; `get_dashboard_summary()`'s overview branch gained an optional `school_id` filter.
- `app/schemas/admin.py`, `app/services/admin.py`, `app/routers/admin.py` (new): the full admin API. No new dependency -- `python-multipart` (for `UploadFile`) was already added in ADR-016.
- `scripts/seed_dev_data.py`: provisions and prints a dev teacher account.
- `frontend/src/App.jsx`, `frontend/src/api.js`, `frontend/src/components/TeacherAdminScreen.jsx` (new), `frontend/src/components/LoginScreen.jsx`, `frontend/src/styles/chat.css`: the admin UI and its three API calls.
- `backend/tests/test_admin.py` (new): pure unit tests for `parse_student_csv()` and `get_current_teacher()`'s role check. The parsing logic was additionally verified by running it directly in this sandbox against the exact same assertions (the sandbox can't import the full `app` package -- no `pgvector`/`pydantic_settings` env -- so this is the same "verify what can be verified here, hand the rest to Siya's real venv" posture every prior segment has used).

## Open items (explicitly not done, not silently dropped)

- **No in-product way to create a school's first teacher account.** `scripts/seed_dev_data.py` remains the only way, same posture ADR-017 took for a school's first anything.
- **The dashboard's own mastery/risk views are not wired into `TeacherAdminScreen` yet.** This pass closes the auth gate and the provisioning gap specifically; surfacing `GET /api/v1/dashboard/*`'s data in the teacher UI is a natural next step, not built here.
- **Not live-tested against a real Claude/browser session yet** -- handed to Siya next, same discipline as every prior feature. In particular: the actual login → TeacherAdminScreen → add-student → log out as that student flow has only been verified by reading the code and bundling it with esbuild, not by a human clicking through it.
- **No rate-limiting on bulk CSV upload size or frequency** -- a teacher could upload an arbitrarily large file; fine for a pilot, not hardened.
- **No de-duplication against an existing roster** -- re-uploading the same CSV twice creates two full sets of accounts. Deliberate (not guessing at what a teacher meant by a duplicate name), but worth knowing before a real school uses this.
- **`sessionStorage` token storage** (ADR-017's own documented simplification) now also covers teacher sessions -- not re-litigated here.
