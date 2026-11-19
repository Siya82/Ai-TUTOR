# ADR-043 — Verifying that a parent is the learner's parent or guardian

**Date:** 19 Nov 2026 · **Status:** Accepted

## Context

Until now a parent got a CONNECT login only from the school (ADR-038), so the
school vouched for every parent. Siya asked how to verify parents if they sign
themselves up, the way d6 Connect does. Anyone can claim to be a learner's
mother, so the claim on its own proves nothing.

## Decision

THUTOra never decides who is a parent. **The school's own record decides.**

1. **Guardian contacts on the learner record.** Staff (management, or the
   learner's own teachers) record each parent/guardian's name, relationship,
   cellphone and optional email, as on the enrolment form or in SA-SAMS. The
   CSV bulk upload also accepts `guardian_name`, `guardian_relationship`,
   `guardian_cellphone` and `guardian_email`. Numbers are stored as +27….
2. **Cellphone sign-up, which only links on a match.** A parent picks the
   school and enters their cellphone. A 6-digit SMS code is sent only if that
   number is a guardian contact of an active learner at that school. The reply
   is the same either way, so nobody can find out which numbers a school
   holds. The code (hashed with HMAC, 10 minutes, at most 5 tries, single
   use) proves they own the number. Being on the school's record proves the
   number belongs to the parent. They are linked to every child with that
   number, and their login number is their cellphone (e.g. 0821234567).
   Doing it again with a verified code also resets a forgotten password.
   Codes are limited to 3 per number and 20 per IP per hour.
3. **Viewers approved by a guardian.** A guardian can create a one-time invite
   code (XXXX-XXXX, 7 days) for a grandparent or carer. The viewer gets their
   own login and sees progress. They do not see school notices, and they
   cannot invite others. The guardian can remove them at any time.
4. **The school can always override:** it can edit or remove contacts,
   unlink parents (guardian or viewer), and switch logins off. The existing
   school-issued parent login (ADR-038) still works for families without
   cellphones.

SMS sign-up is switched on only when an SMS provider exists (`SMS_PROVIDER`
in `.env`). In development the provider is "console": the code is written
to the backend log (`DEV SMS to +27…`). It is never console in production.
Without a provider the sign-up link is hidden. Viewer invites need no SMS.

## Consequences

- New tables: `learner_guardians`, `signup_codes`, `viewer_invites`.
  `parent_links` gains `kind` ("guardian"/"viewer") and
  `invited_by_user_id` (migration 0018).
- Data quality matters: a wrong number on file means the parent can't sign
  up, and a parent should ask the school to correct it. That is the
  intended failure mode, rather than linking the wrong person.
- Deleting a learner's data (ADR-037) also removes their guardian contacts
  and invites.
- Still to do: choose an SMS provider (e.g. Clickatell, BulkSMS or
  Twilio) and implement it in `app/services/sms.py`; import guardian contacts
  from SA-SAMS once a sample export is available.
