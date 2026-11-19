# ADR-038: CONNECT — parent logins, child progress, school notices

**Date:** 19 Nov 2026 · **Status:** Accepted

## Decision
- **Parents are users** with role `parent` in the child's school, logging in
  with a school-issued number like staff. Staff create the login from a
  learner's row (Students → Parents), shown once with a one-time password, or
  link an existing parent login (siblings). `parent_links`, migration 0016.
- **What parents see:** this week's practice (answers, days, accuracy), strong
  and weak topics (60 days, at least 3 answers), and school work with marks
  only where the learner can see them (tests after release). **Never the
  child's tutor conversations** — that is the learner's own space.
- **Summary in the parent's language:** a few plain sentences built from the
  numbers, translated with Claude (cheaper `MARKING_MODEL` if set) into any of
  the 11 official languages, cached per child/language/day, with an English
  fallback and an "in English" toggle.
- **Notices:** management posts notices to all parents or one grade, with an
  optional "I've read this"; the school sees "N of M" read. `school_notices`,
  `notice_acks`.
- Deleting a learner also removes their parent links; a deactivated learner
  disappears from the parent view.

## Later
WhatsApp/SMS delivery of the weekly summary and notices needs a messaging
provider account; the content and acknowledgement model are ready for it.
