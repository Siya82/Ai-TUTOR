# ADR-022: Scale Pure Mathematics, Physical Sciences, and Accounting to Grade 12

**Status:** Accepted
**Date:** 15 November 2026

## Context

Siya's own stated plan, going back to the Accounting Grade 11 addition (ADR-019):
scale Pure Mathematics, Physical Sciences, and Accounting to Grade 12 once the
isiZulu accuracy issue (ADR-021) was in a workable state. His explicit direction
this session: pause isiZulu Home Language work (ADR-021's RAG ingestion pipeline
is mid-flight and deliberately untouched here) and proceed with the rest of the
Grade 11/12 scale-up, which bundles these three subjects' Grade 12 additions
together as one directive, same as ADR-020 bundled English+isiZulu together as
one conceptual decision.

Each subject's real DBE CAPS Grade 12 Annual Teaching Plan was researched before
writing any seed data (education.gov.za CAPS FET documents, checked 15 Nov 2026),
same discipline as every prior addition.

## Decision

**Pure Mathematics (12 topics, 24 questions):** follows the CAPS Grade 12 ATP's
own term order (sequences/series and functions in Term 1, calculus and
analytical geometry in Term 2, Euclidean geometry/statistics/probability in
Term 3). Confirmed Linear Programming is NOT part of the current CAPS
curriculum (removed in an earlier revision) -- not omitted by oversight.
Topics that are a genuine, identical-skill deepening of their exact Grade 11
counterpart reuse that exact name (Finance, Growth and Decay; Analytical
Geometry; Euclidean Geometry -- the same convention Grade 11 itself used for
its own Grade 10 counterparts). Topics where CAPS introduces a materially new
sub-skill get a new, more specific name instead (Functions -> "Functions and
Inverse Functions"; Trigonometry -> "Trigonometry: Compound Angles" -- the same
naming pattern Grade 11's "Exponents and Surds" already set). Three chains: a
Functions/Polynomials/Calculus chain, a Trigonometry chain, and independently
cross-grade-anchored topics.

**KNOWN OPEN RISK, flagged before any live test:** Differential Calculus
introduces notation (`f'(x)`, first-principles limits) no prior Maths or
Physical Sciences content has used. A check of `math_validator.py` found zero
existing handling for derivative or limit notation -- not confirmed broken, not
confirmed working, genuinely untested. Consistent with this project's "don't
guess a fix before a real failure" discipline (every real MathGuard gap found
so far was found by testing against real content, not by guessing upfront), no
speculative fix is included. This is the single most likely candidate for a new
MathGuard gap once live-tested.

**Physical Sciences (7 topics, 14 questions), Physics strand only** -- same
strand-only scoping as Grade 10/11 (ADR-013). A Mechanics chain (Momentum and
Impulse -> Vertical Projectile Motion -> Work, Energy and Power, matching CAPS'
own Term 1 order); Doppler Effect, anchored directly to Grade 10's "Waves,
Sound and Light" since no Grade 11 Waves topic exists in this project at all
(Grade 11 Physical Sciences deliberately didn't build a Waves strand -- see
ADR-015); Electric Circuits (reused name -- Grade 12 adds internal resistance
and series-parallel networks); Electrodynamics (anchored to Grade 11
Electromagnetism); and Photoelectric Effect (anchored to Grade 10's
Electromagnetic Radiation, since the EM-spectrum/photon-energy basics are
Grade 10 content and only the photoelectric effect itself is new at Grade 12).

**Accounting (12 topics, 24 questions):** Companies is a whole new business
entity, so it gets its own linear trunk (Concepts and Ledger Accounts -> Final
Accounts and Year-End Adjustments -> Financial Statements -> Cash Flow
Statement -> Analysis and Interpretation of Financial Statements), the same
"new entity gets its own trunk" shape ADR-019 used for Partnerships at Grade 11.
Five topics are a genuine deepening of their exact Grade 11 counterpart and
reuse that exact name (Fixed Assets, Inventory Systems, Value-Added Tax (VAT),
Manufacturing Cost Accounting, Budgeting (Cash Budget) -- the same convention
ADR-019 used for Budgeting/VAT). CAPS' three separate Grade 12 reconciliation
types (bank, debtors, creditors) are merged into one topic,
"Reconciliations (Bank, Debtors and Creditors)", anchored to Grade 11's Bank
Reconciliation. Close Corporations gets no cross-grade anchor -- deliberately,
the same "no clean counterpart" judgment call ADR-019 made for Fixed Assets at
Grade 11. Verification stance unchanged from ADR-018/ADR-019: still no
MathGuard-style checking.

**Cross-grade anchoring verified programmatically, not assumed:** every
`(subject_name, grade, topic_name)` reference across all three subjects was
checked by script to resolve to a real, already-seeded topic name before this
commit -- the same verification discipline ADR-014 established.

## Consequences

- `backend/scripts/seed_dev_data.py`: three new `SUBJECTS` entries (Pure
  Mathematics grade 12, Physical Sciences grade 12, Accounting grade 12), each
  with its own `_..._GRADE12_TOPICS`/`_..._GRADE12_QUESTIONS` pair. No model or
  migration change.
- `frontend/src/components/SymbolKeyboard.jsx`: 9 new entries for Pure
  Mathematics Grade 12 (topics with a materially new skill), 6 new entries for
  Physical Sciences Grade 12, 6 new entries for Accounting Grade 12. Topics
  reusing an exact Grade 11 name correctly need no new entry, confirmed by a
  cross-check script, not assumed.
- `app/services/tutor.py`, `app/routers/topics.py`,
  `frontend/src/components/SubjectTopicSidebar.jsx`: zero changes, confirmed by
  reading the code, same finding as every prior addition.
- `math_guard.py`/`math_validator.py`: zero changes -- see the Differential
  Calculus open risk above.

## Open items (explicitly not done, not silently dropped)

- **Differential Calculus's notation is untested against MathGuard.** The
  single most likely new gap once this is live-tested -- see Decision above.
- **Not live-tested against a real Claude call yet** for any of the three
  Grade 12 additions -- handed to Siya next, same discipline as every prior
  content addition, gated on his local environment completing a clean
  `seed_dev_data.py` run.
- **No Accounting-specific verifier exists** for any Accounting grade.
- This is the final CAPS grade for all three subjects -- there is no Grade 13.
  Future expansion for these three subjects means new subjects/strands (e.g.
  the deferred Physical Sciences Chemistry strand, ADR-013), not new grades.
