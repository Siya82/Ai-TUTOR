# ADR-051 — ADMIN by role, and a THUTOra Console for Zynora staff

**Date:** 23 Nov 2026 · **Status:** Accepted, both parts built (23 Nov 2026)

## Context

Siya asked two questions:
- Should THUTOra Support be a sixth product next to LEARN, TEACH, CONNECT,
  ADMIN and INSIGHTS?
- Does the school admin need an app of their own?

## Decision

### 1. No separate app for the school admin. ADMIN fits the role instead (built)

ADMIN is already the school's app for the principal, deputy and school admin
(ADR-044). The server rules don't change: a school admin may manage the whole
school but can't see marks or give roles (ADR-031). A second app would split
one school's work across two logins.

What changes is where ADMIN opens:
- **Principal or deputy** (even if also school admin): Overview first, as
  before.
- **School admin only**: Learners first, then Classes, Staff, Notices,
  Overview, School settings and Activity. Their daily work is registering
  learners, fixing rosters and resetting passwords.

Every tab stays available to every manager. The landing tab waits for
`/school/me`, so the Overview doesn't flash up first.
Code: `utils/staff.js` (`ADMIN_TAB_ORDER`, `adminFocus`, `adminLandingTab`)
and `AdminScreen.jsx`. Tabs now carry `aria-current="page"`.

### 2. Support isn't a customer product. Zynora gets an internal console (built)

Customers keep getting help inside the product they're using: the Help
button and tickets from ADR-050. Sending a teacher to another app to get help
would be worse.

Zynora's side is command-line scripts today:
- `scripts/support.py`;
- `provision_school`;
- `manage_registrations`;
- `manage_insights`.

These are fine while Siya is the only support person. They're risky with
more people: easy to mistype, not in the activity log, and they need direct
database access.

**THUTOra Console** is an internal web tool for Zynora staff. It isn't part
of the product family, isn't sold, and isn't shown to schools. Scope:
- ticket queue: list, read, reply, set priority, resolve;
- school registrations: review, approve (principal or school admin);
- provision a school;
- give or remove a principal role; assign or remove an education official
  (closes the "no remove tool" gap);
- every action written to an audit log with the Zynora staff member's name
  (closes the "script actions not logged" gap);
- read-only school lookup: name, EMIS, status, staff count. No learner
  marks, and no tutor conversations, ever (ADR-050's "never" rules).

Security, stricter than the school apps:
- its own web address, not linked from the school apps;
- Zynora staff accounts kept apart from school accounts;
- a second sign-in step, such as a phone code;
- short sessions;
- Zynora staff roles (agent, lead, director), so one person no longer holds
  every tool.

**When:** Siya asked for it the same day, so it was built straight away.

### 3. How the Console connects to THUTOra (built)

**One API, one database, a separate website.** There's no second server:
- The API has a new `/console` section (`app/routers/console.py`). The
  Console website (`console/`, its own Vite app on port 5174, its own
  Firebase site in production) calls only that.
- **Separate accounts.** Zynora staff are rows in `console_staff`, not
  `users`. Email + password, then a 6-digit code from an authenticator app
  (TOTP, RFC 6238, `app/services/totp.py`). No SMS provider is needed, and a
  code can't be used twice.
- **Separate tokens.** Console tokens carry `aud="thutora-console"`. The
  school decoder rejects any token with an audience, and the Console decoder
  requires it, so neither kind opens the other side. Tests check both ways.
  The step-1 token lasts 5 minutes and opens only the code step. A full
  session lasts 30 minutes (`CONSOLE_SESSION_MINUTES`).
- **Address check.** `/console` refuses calls from a school app's address.
  In production it accepts only `CONSOLE_ORIGINS`, and the API won't start
  if that's missing, http, or a school address. `CONSOLE_ENABLED=false`
  turns it all off (404).
- **Roles.**
  - Agent: tickets, and read-only school lookup.
  - Lead: also registrations, setting up schools, principals, INSIGHTS
    structure and officials, and the audit log.
  - Director: also Console staff.
  - Nobody can change their own access.
- **Audit.** Every action is an `audit_events` row with `console_staff_id`
  (migration 0026). Actions on a school also show in that school's
  ADMIN → Activity as "THUTOra support". Ticket replies record which staff
  member answered.
- **Never shown.** There are no Console endpoints for learner names, marks,
  work or tutor conversations. A test fails if a route or a model for them
  is added to the Console router.
- **Shared logic.** `app/services/onboarding.py` now holds approving a
  registration, setting up a school, the first login, and adding or removing
  principals and officials. The Console and the old scripts both call it.
- **Bootstrap.** `python -m scripts.console_staff create --role director`
  makes the first director. The same script resets an authenticator or a
  password if every director is locked out.

The old scripts (`support`, `manage_registrations`, `provision_school`,
`manage_insights`) still work as a fallback. Their actions aren't audited,
so use the Console.

Known limits:
- The authenticator secret is stored as is in the database. It's protected
  by database access; encrypt it with a KMS key at deployment if needed.
- An IP allowlist for the Console site is optional (see RUNBOOK 4c).

## Consequences

- The shared roles doc lists THUTOra Console under the support section, and
  three gaps are closed: support actions are now logged, officials and
  principals can be removed, and support is split into roles.
- The help guides need no change: they describe tabs by name, not by
  position.
- Province and national officials are still a separate piece of work.
