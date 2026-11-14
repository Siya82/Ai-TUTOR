# ADR-017: School-linked student login (real auth, replacing the open `learner_id`)

**Status:** Accepted
**Date:** 2026-11-14

## Context

Every endpoint in THUTOra has, until now, trusted whatever
`learner_id` a request body claimed to be -- there was never any real
authentication (REBUILD_SPEC.md Section 2, step 8, explicitly deferred
since the original rebuild). This was acceptable for a single-dev
pilot but stops being acceptable the moment more than one real
student's data sits in the same database. Siya asked for student
login next, right after the subject/topic sidebar and the logo landed
a natural spot for it on the header. Scoped via three direct answers:

- Students should be **linked to a school**, identified by either a
  school-issued student number or a system-generated one -- left to
  this ADR to decide the concrete shape.
- Provisioning method ("whichever is best for scalability and
  development, with POPIA in mind") -- left to this ADR to decide.
- Data model: build a **real `User`+role table now**, not bolted onto
  the existing `Learner` table -- confirmed explicitly, matching the
  earlier EdPaaS-direction recommendation (teacher/parent/admin roles
  are still on the roadmap, and reworking an auth system bolted onto
  `Learner` later would be far more disruptive than building the
  separation now while there's only one role to migrate).

## Decision

### New tables: `schools` and `users`

- `schools`: `id`, `name`, `created_at`. Minimal on purpose -- enough
  to scope students, nothing else is needed yet.
- `users`: `id`, `role` (string, `"student"` for now -- deliberately
  not a DB enum, so adding `"teacher"`/`"parent"`/`"admin"` later is a
  data change, not a migration), `school_id` (FK to `schools`),
  `student_number` (string), `password_hash`, `is_active`,
  `must_change_password` (bool, see provisioning below), `created_at`.
  `UniqueConstraint("school_id", "student_number")` -- a student
  number only has to be unique *within* its own school, matching how
  real school-issued numbers actually work (two different schools
  will absolutely reuse the same numbers).
- `learners.user_id` (nullable FK to `users`, unique): the existing
  pedagogical `Learner` row (preferred_modality, grade, attempts,
  attachments, sessions -- all already wired throughout the app) stays
  exactly as it is and is now *owned by* a `User` for auth purposes,
  rather than being merged into it. This is the whole point of
  "User+role table, not bolted onto Learner" -- `Learner` is a
  domain profile, `User` is an identity/credential, and the FK is the
  seam between them. Nullable for now so existing dev data doesn't
  need a forced migration path immediately, but every real student
  going forward gets both rows created together by provisioning.

### Student number: school-issued OR system-generated, same column either way

If a school supplies real student numbers at provisioning time, those
are stored verbatim. If not (or for an ad-hoc/demo account), the
system generates one (`app/services/auth.py`'s
`generate_student_number()`: a short random alphanumeric code, checked
against the `(school_id, student_number)` uniqueness constraint with a
retry loop). Login always asks for the same three things either way:
**school, student number, password** -- the student and the frontend
never need to know or care which case produced the number.

### Provisioning: pre-created accounts, not self-signup

Chosen for both halves of what Siya asked for:

- **POPIA, specifically:** these are minors. Self-signup would mean
  collecting personal information (whatever the signup form asks for)
  directly from a child with no verified parent/guardian/responsible-
  adult involvement -- exactly the processing POPIA's children's-data
  provisions (s35) are stricter about. A school (or, for now, Siya)
  creating the account on the student's behalf keeps the data
  collected to the minimum needed (school + student number; no email,
  no self-reported personal details) and keeps a real institution in
  the loop as the party that enrolled the student, rather than an
  anonymous open form on the internet collecting from whoever lands on
  it.
- **Scalability:** a school's admin (or Siya, standing in for that
  role today) can provision many students at once -- a bulk-import is
  a natural fit for "many rows from a school's own records," not
  "every student successfully completes a signup flow themselves."

Mechanics: `app/services/auth.py`'s `provision_student()` creates the
`School` (if needed), the `User` (with a random temporary password if
none is given, `must_change_password=True` in that case), and the
linked `Learner`, returning the plaintext temporary password *once*,
to be handed to the student out-of-band (this is the only point the
plaintext password ever exists outside the student's own head -- it's
never logged, stored, or re-displayed). `scripts/seed_dev_data.py`
calls this directly for one demo school/student, printing the
temporary password to the console for local dev login. A real
bulk-provisioning admin endpoint (`POST /schools/{id}/students/bulk`
or similar, once a school-admin role exists) is the natural next step
once there's a UI/role to drive it from -- out of scope for this pass,
but `provision_student()` is written as the seam that endpoint would
call.

### Login and sessions

`POST /auth/login` takes `{school_id, student_number, password}`,
verifies the hash (`passlib[bcrypt]`, pinned `bcrypt==4.0.1` per the
known passlib/bcrypt 5.x incompatibility already flagged in
`requirements.txt`'s own comments), and returns a short-lived JWT
access token (`python-jose`, HS256, secret from a new required
`JWT_SECRET_KEY` setting -- **never** hardcoded, same treatment as
`ANTHROPIC_API_KEY`) plus the linked learner's profile and the
`must_change_password` flag. `POST /auth/change-password` lets a
student set their own password on first login (requires the current
-- possibly temporary -- password, matching normal "change password"
semantics rather than a bare reset). A new `get_current_learner`
FastAPI dependency decodes the bearer token on every subsequent
request and resolves straight to the `Learner` row -- this *replaces*
`learner_id` in the `/tutor/message` and `/attachments` request
bodies entirely. This is the actual fix for the long-deferred step 8
gap: those endpoints no longer trust a client-supplied ID at all.

Token storage on the frontend is `sessionStorage` (survives a page
refresh within the same tab, cleared on tab close) rather than a
proper httpOnly refresh-token cookie flow. **Documented simplification,
same discipline as MathGuard's own honest gaps:** sessionStorage is
readable by any JS on the page (an XSS risk a refresh-cookie flow
would close), and there's no token refresh -- a session simply expires
after the access token's lifetime and the student logs in again. Fine
for a single-school pilot; worth hardening before this app handles
real production traffic across many schools.

## Consequences

- New dependencies, already anticipated in `requirements-baseline.txt`
  on Siya's new laptop and now actually pinned in
  `backend/requirements.txt`: `passlib`, `bcrypt==4.0.1`,
  `python-jose[cryptography]`.
- New required setting: `JWT_SECRET_KEY` (no default -- the app
  refuses to start without one, same posture as `ANTHROPIC_API_KEY`).
  Siya needs to add this to `backend/.env` himself; see
  `docs/LOCAL_SETUP.md`.
- Breaking change to `/tutor/message` and `/attachments`: both
  endpoints drop `learner_id` from their request bodies and require an
  `Authorization: Bearer <token>` header instead. Any existing script
  or manual test call that posts a raw `learner_id` needs updating.
- `GET /learners` (used today by the frontend to auto-pick "the first
  learner") is no longer part of the student chat flow -- the frontend
  now logs in and gets its learner identity from
  `POST /auth/login`/`GET /auth/me` instead. The endpoint itself is
  left in place (a future teacher/admin dashboard will want to list
  learners), just no longer called from `ChatScreen.jsx`.
- Not done in this pass: a real bulk-provisioning admin endpoint or
  UI (schools/students are provisioned via `provision_student()`
  called directly, e.g. from the seed script, not through an HTTP
  API yet); token refresh/httpOnly-cookie hardening; rate-limiting on
  `/auth/login` (a real gap for a public login endpoint -- noted here
  so it isn't forgotten, not silently left out); teacher/parent/admin
  roles themselves (the `role` column exists and is designed for this,
  but only `"student"` is implemented).
