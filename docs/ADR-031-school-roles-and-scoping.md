# ADR-031: School and education-system roles, and how they scope access

**Status:** Accepted (school tier built now; circuit and above designed, not built)
**Date:** 17 November 2026

## Context

Until now every teacher in a school saw every learner in that school: the
Students tab, Progress (ADR-030) and the assignment student picker were all
scoped by `school_id` only. There was also no way to create staff accounts in
the product, and no notion of what a teacher actually teaches.

Siya set out the hierarchy he wants (teacher → HoD → principal → circuit
manager → district manager → DoE/MEC, each seeing only its own scope, with
access granted by the person each role reports to). It was reviewed against
the South African system before designing anything. The corrections, agreed
by Siya:

1. **Teachers are allocated, and the school allocates them.** The unit is a
   *teaching allocation*: subject + grade + class ("Pure Mathematics, Grade 10,
   10A"). A teacher can hold several, and they change every year. The
   principal or school management decides them, not Zynora's app admin.
2. **A teacher sees only their allocations.** Their classes' learners, and
   only those learners' data in the allocated subject (POPIA data
   minimisation for minors).
3. **"HoD" means two different things.** In a school it is a *departmental
   head*, scoped by subject department (e.g. Mathematics and Physical
   Sciences), optionally limited to a grade. In a province it is the *Head of
   Department*, the province's most senior official. The app calls the school
   role **departmental head**.
4. **Principal (and deputy principal) see the whole school.** The deputy was
   missing from the original list.
5. **Circuit managers support and supervise principals.** They need read and
   oversight across their circuit's schools, not "all privileges". They must
   not edit teachers' assignments or marks, and mostly need aggregates.
6. **District director** oversees all circuits and schools in the district.
   **Subject advisors** were missing: they support one subject across every
   school in a district.
7. **Province and national.** The MEC is the political head and receives
   reports; officials hold data access. National DBE needs national
   aggregates only. "Approved by the person you report to" is right, but the
   top of each tree can't be approved in-app: it starts with a signed
   agreement between the institution and Zynora (which also makes Zynora an
   operator under POPIA).

Also missing: parents (CONNECT), a school admin clerk, and a Zynora platform
admin who sets up organisations but does not routinely see learner data.

## Decision

### The model (all tiers)

Every grant is **who + role + where + optional filter**:

| Part | Values |
|---|---|
| Who | a `User` |
| Role | teacher (via allocations), departmental_head, deputy_principal, principal, school_admin; later: subject_advisor, circuit_manager, district_director, provincial_official, national_official, parent |
| Where | class → school → circuit → district → province → national |
| Filter | optional subject and/or grade |

Two rules apply everywhere:

- **Editing stays at school level.** Only school staff create assignments and
  mark work. Every role above the school reads and monitors.
- **Detail shrinks going up.** Learner-level detail inside the school,
  per-school summaries above it, only what's needed at province and national
  level.

**Granting:** a user can only grant roles within their own scope and below.
The first principal of a school is created by Zynora's onboarding script
(`scripts/provision_school.py`), standing in for the signed agreement.

### What's built now (school tier)

**Tables (migration 0008):**

- `users.display_name` (nullable). Staff need a name; students keep theirs on
  `Learner`.
- `school_classes` (school, name, grade; name unique per school) and
  `class_members` (class, learner). A learner can be in several classes
  (e.g. a register class and subject groupings).
- `teaching_allocations` (teacher, subject, class). The `Subject` row already
  carries the grade, and must match the class's grade.
- `staff_roles` (user, school, role, optional `subject_name`, optional
  `grade`). Used for principal, deputy_principal, departmental_head and
  school_admin. A departmental head of "Mathematics and Science" gets one row
  per subject name (e.g. "Pure Mathematics", "Physical Sciences").

`User.role` stays `"student"` or `"teacher"`; `"teacher"` now means "school
staff account". What a staff member can do comes from their allocations and
staff roles, resolved per request by `app/services/school_scope.py`.

**What each role can see and do:**

| Role | Roster (names) | Academic data and assigning | Manage school* | Can grant |
|---|---|---|---|---|
| Teacher (allocations only) | learners in their allocated classes | those learners, allocated subject(s) only | no | nothing |
| Departmental head | learners in the department's grade(s) | department subjects, those grades | no | nothing |
| Deputy principal | whole school | whole school, all subjects | yes | departmental_head, school_admin |
| Principal | whole school | whole school, all subjects | yes | deputy_principal, departmental_head, school_admin |
| School admin (clerk) | whole school | **none** | yes | nothing |

\* Manage school = add students (single and CSV), create staff accounts,
create classes and set members, create and remove teaching allocations.

A person can hold several of these (a principal who also teaches 12A
Mathematics). Their access is the union.

**Enforcement is on the server, not the screens** (same rule as ADR-024 and
ADR-026):

- `GET /admin/students` returns only roster-visible learners. Adding students
  requires manage-school.
- `/api/v1/dashboard/*` (overview, progress, learner detail, mastery, risk)
  returns only academically visible learners, and only attempts on subjects
  the viewer may see for that learner. Progress gains a `class_id` filter.
- Creating an assignment checks every target learner against every question's
  subject. A teacher can't assign a Physical Sciences question to a learner
  they only teach Mathematics. Assignments can now also target whole classes
  (`class_ids`), expanded on the server.
- Assignments stay private to the teacher who created them (unchanged).
- A new `/school/*` router covers scope (`GET /school/me`), classes,
  members, staff, roles and allocations.

### Not built yet (designed above)

Circuit, district, province, national, subject advisor and parent roles. They
need `circuits`/`districts`/`provinces` tables, `schools.circuit_id`, and
aggregate-only reporting. That arrives with INSIGHTS (ADR-025). Also not
built: a principal viewing other teachers' assignments, an audit log of role
grants, and year rollover of classes and allocations.

## Consequences

- **Behaviour change:** a staff account with no allocations and no role now
  sees no learners. On an existing database the dev teacher `T00001` is
  re-seeded with an allocation (Pure Mathematics, Grade 12, class 12A,
  containing the dev learner), and a new dev principal `P00001` is seeded.
- Bulk CSV upload doesn't assign classes yet. Students are added to classes in
  the School tab afterwards.
- Learners who aren't in any class are visible only to whole-school roles and
  departmental heads, which is the correct default for a newly uploaded
  learner.


## Follow-up (17 Nov 2026): several subjects and grades in one step, and whole-grade allocations

Siya asked for the principal to be able to give a teacher different grades
and different subjects. One-at-a-time, class-only allocation made that slow,
and it was impossible before classes existed. Two changes:

- **Whole-grade allocations** (migration 0012: `teaching_allocations.class_id`
  is now nullable). No class means the teacher teaches that subject to
  **every learner in the subject's grade** at the school, with no classes
  needed. `build_scope()` grants exactly that subject for those learners. A
  whole-grade teacher also sees that grade's classes (for class targeting and
  the Progress class filter).
- **Bulk allocation**: `POST /school/allocations/bulk` with
  `{teacher_user_id, items: [{subject_id, class_id|null}]}`. Each item is
  validated on its own. Duplicates and grade mismatches are reported in
  `skipped`, not fatal. The School → Staff form now picks subjects ×
  grades × (whole grade | specific classes), previews what it will add, and
  submits once. Subjects not offered in a chosen grade are listed as "not
  possible" instead of being sent.

Single-allocation `POST /school/allocations` keeps working (with an optional
`class_id`). Duplicate checks treat "whole grade" as its own target, because
Postgres unique constraints don't compare NULLs.
