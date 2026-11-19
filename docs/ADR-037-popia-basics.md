# ADR-037: POPIA basics — notice, consent, access and deletion

**Date:** 19 Nov 2026 · **Status:** Accepted (notice text is a DRAFT for legal review)

## Context
Learners are children under POPIA. The code review listed consent, a privacy
notice and data deletion as missing.

## Decision
- **Privacy notice** (`PrivacyNotice.jsx`), linked from login, learner
  Settings, the parent and official views. Version `2026-11-19`
  (`PRIVACY_NOTICE_VERSION`). Items in [brackets] must be completed by Zynora
  (company details, Information Officer, retention period, hosting location,
  Anthropic terms) before go-live.
- **Consent records** (`consent_records`, migration 0015): the school records a
  parent/guardian's consent (who, relationship, how, notice version, who
  recorded it) and its withdrawal. Students tab shows a Consent column.
  Management or the learner's own teacher may record it.
- **Access (s23):** management can download everything held on a learner as
  JSON (profile, tutor conversations, answers, uploads list, consents).
- **Deletion (s24):** management can delete a learner and every linked record
  and uploaded file; the learner's name must be typed to confirm, and files
  are removed only after the database commit.

## Open decision for Siya
Learners without consent are flagged, not blocked. Whether THUTOra should
refuse tutoring until consent is recorded is a policy choice for each school
(or for Zynora's terms).
