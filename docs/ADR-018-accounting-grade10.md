# ADR-018: Add Accounting (Grade 10) as a new subject

**Status:** Accepted
**Date:** 14 November 2026

## Context

Siya chose Accounting (Grade 10) as THUTOra's next subject (via `AskUserQuestion`,
over Grade 12 Pure Mathematics, Grade 12 Physical Sciences, and Life Sciences) --
the first genuinely new subject added since Physical Sciences (ADR-013), and the
third of the four subjects named in the THUTOra brand vision (Mathematics,
Physical Sciences, Life Sciences, Accounting) to actually get engineering scope.

Every subject added so far -- Pure Mathematics, Physical Sciences (Physics
strand) -- shares one property that made MathGuard's sympy-based verification
apply cleanly: the content reduces to "solve this equation" or "evaluate this
formula for x," which is exactly the shape sympy's solve/equality-checking
machinery was built for. Accounting does not share that property. Its CAPS
Grade 10 content (per the DBE's own Annual Teaching Plan and the Via Afrika
Grade 10 study guide, both checked 14 Nov 2026) is: accounting concepts/GAAP/
ethics/internal control (purely conceptual), the accounting equation, cash and
credit subsidiary journals, the general ledger and trial balance, VAT, salaries
and wages, year-end adjustments, financial statement preparation, and budgeting.
Some of this is numeric (VAT percentages, trial balance totals, net salary
arithmetic), but the *check* that matters for most of it isn't "does this
equation have this solution" -- it's "does this ledger balance," "do debits
equal credits," "was this journal entry posted to the correct account" --
structurally different questions MathGuard's equation-solving model doesn't
answer as-is.

## Decision

**Scope: ship the full CAPS Grade 10 Accounting syllabus, not a narrowed
subset.** This is a deliberate departure from ADR-013's precedent (Physical
Sciences shipped Physics-strand-only, explicitly excluding Chemistry because
most Chemistry content isn't equation-shaped and extending the brand to a
subject MathGuard couldn't protect was judged worse than not extending). That
reasoning doesn't carve a clean line here: there is no equation-shaped subset
of Accounting worth shipping alone and a non-equation-shaped subset worth
deferring -- the whole subject has the same basic verification shape (ledger/
balance-style correctness, not equation-solving), so narrowing the curriculum
itself would just lose real CAPS content without buying back any verification
coverage. Ten topics, following the DBE ATP's own term order:

1. Accounting Concepts, GAAP and Internal Control (Term 1)
2. The Accounting Equation (Term 1)
3. Cash Journals (CRJ, CPJ, PCJ) (Term 1)
4. Credit Journals (DJ, DAJ, CJ, CAJ, GJ) (Term 1)
5. General Ledger and Trial Balance (Term 1)
6. Value-Added Tax (VAT) (Term 2)
7. Salaries and Wages (Term 2)
8. Year-End Adjustments (Term 2/3)
9. Financial Statements (Income Statement and Balance Sheet) (Term 3)
10. Budgeting (Cash Budget) (Term 4)

Two topics named in the ATP -- "Debtors and Creditors Reconciliation" and
"Analysis and Interpretation of Financial Statements" (ratios) -- and Term 3's
introductory Cost Accounting are deliberately deferred, not silently dropped:
each is a genuine CAPS Grade 10 topic, but each also depends on machinery
(a reconciliation workflow, a ratio-formula bank, cost-classification rules)
that's cleaner to add once the first ten topics are live and tested, same
"ship the backbone, extend it" pattern ADR-014/015 used for Grade 11 Maths/
Physical Sciences.

**Verification: taught WITHOUT MathGuard-style checking for now, not silently
claimed as verified.** This mirrors the "honest, permanent-until-revisited
limitation" REBUILD_SPEC.md already documents for Euclidean Geometry proofs
(not equation-shaped, not verified, still taught) rather than ADR-013's
"exclude the unverifiable part" call -- the difference is that Geometry proofs
are a small fraction of one Maths topic, while an accounting-shaped check
would need to span nearly all ten Accounting topics, which is new verification
*infrastructure*, not a tweak to the existing one. Building that infrastructure
now, before any Accounting content has been live-tested even once, would repeat
the exact mistake ADR-016/017's own build discipline exists to avoid (every
real MathGuard gap found this project was found by testing against real
content, not by guessing upfront what a checker needs). So: ship the content
first, `math_verified`/`verification_warnings` will report whatever MathGuard's
existing equation-parser naturally does with Accounting-flavored text (most
likely: nothing to check, reported honestly as such, not a false "verified"),
and a dedicated Accounting verifier is explicitly future work, informed by
what live testing actually surfaces -- see Open items below.

**No cross-subject prerequisite links to Maths or Physical Sciences.**
Unlike Grade 11 Maths/Physical Sciences (ADR-014/015), which anchor their
first topics back to a Grade 10 counterpart in the *same* subject, Accounting
is a different skill domain from either existing subject with no natural
foundational dependency either way -- the root-cause diagnosis engine's
prerequisite walk stays entirely within Accounting's own ten-topic chain.

**No new subject-keyboard-worthy symbols, but a small convenience row
anyway.** `SymbolKeyboard.jsx` already falls back to `COMMON_SYMBOLS` alone for
any unmatched topic name, so this subject would have worked with zero frontend
changes. Added a two-button row (R, %) shared across all ten topics regardless,
since every single one deals in Rand amounts and percentages and neither is a
single keystroke on a standard keyboard -- a real, if small, usability gap the
existing Physics-topic rows already treat as worth a dedicated row.

## Consequences

- `backend/scripts/seed_dev_data.py`: new `_ACCOUNTING_TOPICS`/
  `_ACCOUNTING_QUESTIONS`, one new `SUBJECTS` entry. No model or migration
  change -- `Subject`/`Topic`/`Question` are already subject-agnostic (ADR-013).
- `frontend/src/components/SymbolKeyboard.jsx`: ten new `TOPIC_SYMBOLS` entries
  (R, %), one per Accounting topic name.
- `app/services/tutor.py`'s subject-aware prompt builder, `app/routers/topics.py`'s
  `subject_id` filter, and the frontend's `SubjectTopicSidebar.jsx` all needed
  **zero changes** -- confirmed by reading them before writing any seed data,
  not assumed: they already key off the DB's own `Subject`/`Topic` rows rather
  than a hardcoded subject list, the exact design ADR-013 put in place for
  this reason.
- `math_guard.py`/`math_validator.py`: **zero changes.** Deliberately not
  touched in this pass -- see Decision above.

## Open items (explicitly not done, not silently dropped)

- **Not live-tested against a real Claude call yet.** Same handoff as every
  previous content addition -- Siya needs to run the updated
  `seed_dev_data.py`, then try a real `/tutor/message` call against an
  Accounting topic, same discipline that caught every real MathGuard gap this
  project has found so far.
- **No Accounting-specific verifier exists.** What such a checker should even
  validate (ledger-balance equality? a trial balance's debit=credit totals? a
  specific VAT/net-salary formula?) is an open design question, deliberately
  left open until live testing shows what's actually worth checking and how a
  student's free-text answer would even be parsed into a checkable claim.
- **Debtors/Creditors Reconciliation, ratio analysis, and Cost Accounting**
  are real CAPS Grade 10 content not yet seeded -- see Scope above.
- **Grade 11/12 Accounting** doesn't exist yet; this ADR only covers Grade 10.
