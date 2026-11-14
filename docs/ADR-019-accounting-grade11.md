# ADR-019: Add Accounting (Grade 11) as a new grade

**Status:** Accepted
**Date:** 14 November 2026

## Context

Siya's explicit next step (over and above resuming Grade 12 content for the other subjects): deepen Accounting the same way Pure Mathematics and Physical Sciences were deepened into Grade 11 (ADR-014/015), before any subject gets scaled to Grade 12. Checked against the real DBE CAPS Grade 11 Accounting Annual Teaching Plan and its Term breakdown (education.gov.za, 14 Nov 2026): Term 1 covers bank and creditors' reconciliations, fixed assets, and partnerships (concepts, formation, and final accounts with year-end adjustments); Term 2 covers partnership financial statements and ratio-based analysis/interpretation; Term 3 covers budgeting, inventory systems, and manufacturing cost accounting; Term 4 deepens VAT (zero-rated/exempt/standard-rated items, the effect of bad debts/discounts/returns, and related ethics).

Grade 11 Accounting is a substantial step up from Grade 10, not a repeat of it: it introduces an entirely new business entity (a partnership, not a sole trader) and the skills that come with two owners (capital/current accounts, profit appropriation), plus ratio analysis and manufacturing costing, neither of which exists in Grade 10 at all. Only a few Grade 11 topics are a direct deepening of an exact Grade 10 skill (VAT, Budgeting); most of Grade 11 is genuinely new content built on top of Grade 10 foundations rather than a repeat of them -- closer in shape to how Grade 11 Physical Sciences related to Grade 10 (ADR-015: only 2 of 6 topics had an exact Grade 10 counterpart) than to Grade 11 Pure Mathematics' clean 1:1 mapping (ADR-014).

## Decision

**Scope: the full Grade 11 ATP, eleven topics, following the DBE's own term order:**

1. Bank Reconciliation (Term 1)
2. Creditors' Reconciliation (Term 1)
3. Fixed Assets (Term 1)
4. Partnerships: Concepts and Formation (Term 1)
5. Partnership Final Accounts and Year-End Adjustments (Term 1)
6. Partnership Financial Statements (Term 2)
7. Analysis and Interpretation of Financial Statements (Term 2)
8. Budgeting (Cash Budget) (Term 3)
9. Inventory Systems (Term 3)
10. Manufacturing Cost Accounting (Term 3)
11. Value-Added Tax (VAT) (Term 4)

Two topic names -- "Budgeting (Cash Budget)" and "Value-Added Tax (VAT)" -- are reused verbatim from the Grade 10 Accounting topic list, same convention Grade 10/11 Pure Mathematics and Physical Sciences already use (a topic name stays the name of the skill, not the grade's version of it): the skill deepens (Grade 11 Budgeting adds the Projected Income Statement and the distinction between it and a Cash Budget; Grade 11 VAT adds zero-rated/exempt items and the effect of bad debts/discounts/returns) without needing a different name. As a side effect this means both topics automatically pick up `SymbolKeyboard.jsx`'s existing Grade-10-added R/% row with zero new frontend code -- see Consequences.

**Prerequisite design: four independent branches, each rooted in its own Grade 10 Accounting topic, not one shared Grade 10 trunk.** This is a deliberate departure from Grade 10 Accounting's own single-trunk-with-branches shape (ADR-018: everything eventually traces back to one root, Accounting Concepts). Grade 11's four skill areas -- reconciliation, partnership accounting, budgeting, VAT -- don't depend on each other the way Grade 10's cash-journals-then-credit-journals-then-ledger chain did; each is better modelled as its own branch anchored directly to the specific Grade 10 skill it actually deepens or requires:

- **Bank Reconciliation** -> cross-grade root: Grade 10's "Cash Journals (CRJ, CPJ, PCJ)" -- you cannot reconcile a cash journal you don't know how to keep.
- **Creditors' Reconciliation** -> cross-grade root: Grade 10's "Credit Journals (DJ, DAJ, CJ, CAJ, GJ)", same reasoning. **Fixed Assets** chains within-grade off Creditors' Reconciliation (continuing Term 1's own teaching order) rather than getting its own cross-grade anchor -- unlike reconciliation, nothing in the seeded Grade 10 Year-End Adjustments content is specifically about depreciation or an asset register, so forcing a cross-grade link there would be the same kind of contrived mapping ADR-015 explicitly avoided for Electromagnetism/Magnetism.
- **Partnerships: Concepts and Formation** -> cross-grade root: Grade 10's "The Accounting Equation" -- a partner's Capital/Current account is a direct extension of the owner's-equity concept taught there, just split across two or more owners. **Partnership Final Accounts and Year-End Adjustments**, **Partnership Financial Statements**, and **Analysis and Interpretation of Financial Statements** chain within-grade off this root in CAPS' own teaching order (concepts -> final accounts -> statements -> ratios), the same "deepen within the grade once you're past the root" shape Grade 11 Maths uses after its own cross-grade roots.
- **Budgeting (Cash Budget)** -> cross-grade root: Grade 10's own "Budgeting (Cash Budget)" (exact-name deepening). **Inventory Systems** and **Manufacturing Cost Accounting** chain within-grade after it, matching the real ATP's Term 3 order (budgeting, then inventory systems, then manufacturing costing) rather than looping back to Term 2's ratio topic.
- **Value-Added Tax (VAT)** -> cross-grade root: Grade 10's own "Value-Added Tax (VAT)" (exact-name deepening), a leaf topic with nothing chained after it, matching Term 4's position as the ATP's final new content before revision.

**Verification: still no MathGuard-style checking, same posture as ADR-018.** Nothing about Grade 11 content changes the equation-shaped/non-equation-shaped analysis ADR-018 already made -- if anything, Grade 11 leans further into non-equation-shaped territory (reconciliation statements, ratio interpretation, qualitative GAAP/ethics questions) than Grade 10 did. `math_guard.py`/`math_validator.py` remain untouched.

## Consequences

- `backend/scripts/seed_dev_data.py`: new `_ACCOUNTING_GRADE11_TOPICS`/`_ACCOUNTING_GRADE11_QUESTIONS`, one new `SUBJECTS` entry placed after the existing Accounting (grade 10) entry (required for `_validate_subject_data`'s cross-grade check -- grade 10 Accounting must already be in `known_subjects` when grade 11's spec is validated). 22 new diagnostic questions (2 per topic), a numeric/conceptual mix matching every prior subject's pattern.
- `frontend/src/components/SymbolKeyboard.jsx`: 9 new `TOPIC_SYMBOLS` entries (R, %) for the topics with no exact Grade 10 name match (Bank Reconciliation, Creditors' Reconciliation, Fixed Assets, Partnerships: Concepts and Formation, Partnership Final Accounts and Year-End Adjustments, Partnership Financial Statements, Analysis and Interpretation of Financial Statements, Inventory Systems, Manufacturing Cost Accounting). The other 2 topics ("Budgeting (Cash Budget)", "Value-Added Tax (VAT)") need **zero** new entries -- they share their exact name with an existing Grade 10 entry, which `TOPIC_SYMBOLS` already keys purely by name, not by subject/grade id.
- `app/services/tutor.py`, `app/routers/topics.py`, `frontend/src/components/SubjectTopicSidebar.jsx`: **zero changes**, same confirmed-by-reading finding as every prior subject/grade addition (ADR-013/014/015/018) -- all three already key off the DB's own `Subject`/`Topic` rows.
- `math_guard.py`/`math_validator.py`: **zero changes.**

## Open items (explicitly not done, not silently dropped)

- **Not live-tested against a real Claude call yet.** Same handoff as every previous content addition -- Siya needs to re-run `seed_dev_data.py` (which will also pick up Grade 10 Accounting if that hasn't run successfully yet, since this is the same idempotent script) and then try a real `/tutor/message` call against a Grade 11 Accounting topic.
- **No Accounting-specific verifier exists for either grade** -- unchanged open item from ADR-018.
- **Grade 12 Accounting** doesn't exist yet. Siya's own stated next step after this is scaling Pure Mathematics, Physical Sciences, and Accounting to Grade 12 -- each will need its own CAPS research pass and its own ADR, same discipline as every grade/subject addition so far, not attempted in this ADR.
