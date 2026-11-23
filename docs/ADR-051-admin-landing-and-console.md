# ADR-051 — ADMIN by role, and a THUTOra Console for Zynora staff

**Date:** 23 Nov 2026 · **Status:** Accepted (part 1 built; part 2 planned)

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

### 2. Support isn't a customer product. Zynora gets an internal console (planned)

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

**When:** before the first pilot school goes live, or before a second person
does support, whichever comes first. Until then the scripts stay.

## Consequences

- The shared roles doc lists THUTOra Console under the support section and
  the gaps.
- The help guides need no change: they describe tabs by name, not by
  position.
- Province and national officials are still a separate piece of work.
