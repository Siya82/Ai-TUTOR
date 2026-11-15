# ADR-027: Dev/admin diagnosis-redirect bypass

**Status:** Accepted
**Date:** 15 November 2026

## Context

ADR-026 (and its Grade-12 follow-up widening `DEV_LEARNER_GRADE`) fixed what the dev/admin account (student number 100001) can *see and access*: it can now browse and be taught any grade, 1 through 12. But Siya's next request made clear that visibility was never the whole problem: *"this profile should have access to all grades... if I choose to request an equation to grade 12 it should treat this profile as already have met all the other grades requirements... it should also apply to grade 11 and 10 and so forth."*

These are two independent mechanisms. Grade visibility/access (ADR-026) is about what `/subjects`, `/topics`, and `POST /tutor/message` will *let through*. Separately, `diagnose_root_gap()` (ADR-007) decides, independent of grade, whether to *redirect* teaching down to a more foundational prerequisite, based purely on the learner's own attempt history on each topic in the chain. The dev/admin account has zero real scored attempts on anything -- it's a troubleshooting tool, not a student who has actually practiced. `diagnose_root_gap()` treats fewer than `MIN_ATTEMPTS_FOR_CONFIRMED_MASTERY` (3) scored attempts on a topic as `"unconfirmed"` -- a possible gap, not a pass -- so with zero attempts everywhere, this account was guaranteed to walk every chain all the way to its deepest prerequisite, every time, for every topic, regardless of ADR-026's grade widening. Asking to be taught Grade 12 Differential Calculus would always actually teach Grade 10 content instead -- fine for a real Grade 12 student with a genuine gap, useless for testing Grade 12 content itself.

## Decision

**A new `Learner.skip_diagnosis: bool` column, default `False`.** When true, `prepare_tutor_turn()` (`app/services/tutor_orchestration.py`) skips the real `diagnose_root_gap()` walk entirely and builds a non-redirected `DiagnosisResult` directly from `prerequisite_chain[0]` -- the topic actually requested. `app/routers/tutor.py`'s earlier, separate "doubled call" to `diagnose_root_gap()` (done before `prepare_tutor_turn()` runs, purely to learn which topic's grounding text to fetch -- see ADR-021) gets the identical bypass, so the two calls can never disagree about which topic is being taught.

**`diagnosis.py` itself is not touched at all.** The real mastery-redirect logic -- a protected differentiator per ADR-011 -- stays completely intact for every real student. This is a per-learner, explicitly flagged, orchestration-layer-only bypass, not a weakening of the diagnosis engine's actual behaviour. `prepare_tutor_turn()` already takes `learner: Learner` as a parameter and reads `learner.preferred_modality` directly off it with no DB call of its own (its own documented DB-free contract); reading `learner.skip_diagnosis` the same way keeps that contract intact.

**`skip_diagnosis=True` only for the dev/admin account**, set by `scripts/seed_dev_data.py`'s `get_or_create_dev_learner()`, both on first creation and (the same "refresh an existing row on re-seed" fix already applied twice this run, for `order_index` and for `DEV_LEARNER_GRADE`) on every re-seed of an already-existing row. Every real student provisioned through the teacher dashboard (ADR-024) keeps the model's default of `False`.

**Rejected alternative: seeding synthetic "confirmed mastery" `Attempt` rows for the dev learner across every topic.** This would have used the existing mechanism with zero new code, but would need fake attempts re-seeded for every topic in every subject at every grade, forever, including every topic any future ADR adds -- a maintenance burden that grows with the curriculum. A single boolean flag, checked once in one place, does not.

## Consequences

- `backend/app/models/__init__.py`: `Learner.skip_diagnosis: Mapped[bool] = mapped_column(Boolean, default=False)`.
- `backend/migrations/versions/0005_add_skip_diagnosis_to_learner.py`: new column, `nullable=False`, `server_default="false"`.
- `backend/app/services/tutor_orchestration.py`: `prepare_tutor_turn()` branches on `learner.skip_diagnosis` before calling `diagnose_root_gap()`.
- `backend/app/routers/tutor.py`: `send_tutor_message()`'s grounding-text preview call gets the matching bypass.
- `backend/scripts/seed_dev_data.py`: `get_or_create_dev_learner()` sets the flag, with the refresh-on-existing-row fix applied.
- `backend/tests/test_tutor_orchestration.py`: two new tests -- `test_skip_diagnosis_teaches_the_requested_topic_with_no_attempt_history` (the bypass actually works, on the exact chain/history that would otherwise redirect) and `test_skip_diagnosis_false_is_unaffected_same_chain_still_redirects` (confirms the flag is opt-in, not a global behaviour change). `_learner()` now takes an optional `skip_diagnosis` parameter.
- Verified with `ast.parse` on every changed/new Python file (same sandbox limitation as always -- no `pgvector`/`pydantic_settings` env here to run the real app). **`pytest` could not actually be run here at all this time, for an unrelated, pre-existing reason**: the sandbox's Python is 3.10, and `tests/test_tutor_orchestration.py` already imports `datetime.UTC` (added in 3.11) -- collection fails on that import before any test, including the two new ones, ever runs. This is not a regression from this change; it means the new tests are unverified by execution here and need a real run (Siya's own machine, or CI) to confirm.

## Open items (explicitly not done, not silently dropped)

- **The two new tests have never actually been executed**, for the Python-version reason above. Siya should run `pytest tests/test_tutor_orchestration.py -v` on his own machine (or CI) and confirm both pass before trusting this ADR's behaviour claim.
- **Not live-tested against a real Claude/browser session yet.** Next step for Siya: `alembic upgrade head`, re-run `python -m scripts.seed_dev_data`, log in as the dev account, and ask a Grade 12 question cold (no prior attempts) -- confirm it teaches the Grade 12 topic directly, with no "DIAGNOSIS NOTE" redirect sentence anywhere in the response.
- **This is a one-way door for exactly one account.** There is deliberately no UI or API path for a real student (or teacher) to set `skip_diagnosis` on themselves or anyone else -- it is only ever set by the seed script, matching the same "two test logins, not a real admin role" posture Siya chose earlier (15 Nov 2026) over building a unified cross-role admin schema.
