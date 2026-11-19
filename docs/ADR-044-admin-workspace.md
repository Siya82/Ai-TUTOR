# ADR-044 — THUTOra ADMIN: the school-management workspace

**Date:** 19 Nov 2026 · **Status:** Accepted

## Context

Running the school (learners, classes, staff and roles, notices) lived in a
"School" tab inside TEACH, beside teaching tools. Siya decided on ADMIN as
a fifth product: a dedicated workspace on the same THUTOra core, not a
separate application. The product family is LEARN (learners), TEACH
(teachers), CONNECT (parents), ADMIN (school management) and INSIGHTS
(officials).

## Decision

- **One platform:** same login, users, school database and permissions
  (StaffScope, ADR-031). ADMIN is a new interface, not new identity.
- **Who gets ADMIN:** principal, deputy principal and school admin
  (`can_manage_school`).
  - A school admin, who has no academic access, only gets ADMIN.
  - Anyone with teaching work also gets TEACH, and switches with the
    TEACH | ADMIN control in the header. The choice is remembered on that
    device.
  - Default: ADMIN for managers without classes, TEACH otherwise.
- **What moved:** "Add student", "Bulk upload" and "School" (classes, staff,
  notices) moved from TEACH to ADMIN. TEACH is now Today, Students,
  Assignments and Progress.
- **ADMIN tabs:**
  - Overview: totals, learners by grade, and a to-do list (learners not in
    a class, classes without a teacher, idle staff accounts, missing
    consent, missing guardian cellphones).
  - Learners, Classes, Staff and Notices.
  - School settings.
- **School settings** (migration 0019):
  - Profile: name, EMIS number, province, quintile, phone, email, address.
  - Two switches that change behaviour: parent cellphone sign-up and family
    viewer invites (ADR-043). Both default to on.
  - Teachers can read the settings; only management can save them.
- **School registration:** "New to THUTOra? Register your school" on the
  login page files a request (rate-limited, numbers checked). It does not
  create an account. Zynora checks the school, then runs
  `python -m scripts.manage_registrations approve <ref>`, which creates the
  school, its profile and the first login (principal by default).
- **Brand:** teal, with Primary #0F766E, Light #14B8A6, Dark #0D5F59 and
  Pale #CCFBF1. On the navy theme the accent is Light, like the other
  products.
  - Lucide `School` is the in-app icon.
  - The illustrated emblem (`thutora-admin-logo.png`, cut from the brand
    sheet) is the product mark.

## Consequences

- Teachers lose nothing they had: they never had add, bulk or school.
- A school admin can't grant roles (ADR-031 GRANTABLE_BY). If a
  registration is approved `--as school_admin`, add the principal later
  with `scripts/provision_school.py`.
- Possible next steps:
  - academic year and terms in settings;
  - a platform-level (Zynora) console for registrations instead of the CLI;
  - an SVG version of the emblem from the designer.
