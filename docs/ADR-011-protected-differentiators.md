# ADR-011: Protected core differentiators

## Date
2026-08-26 (updated same day, twice -- first after Algebra implementation, again after full 12-topic coverage)

## Status
Accepted

## Context
Competitive research found at least seven existing AI tutor products
targeting South African CAPS learners, nearly all claiming "step-by-step
explanations" and CAPS alignment. This framing alone is not differentiated.

Two capabilities were designated protected core differentiators. Both
have moved from architecture, to a single-topic (Algebra) implementation,
to full CAPS Grade 10 Pure Mathematics coverage across all 12 topics --
each stage verified against real Claude output, not assumed to generalize.

## Decision

1. **Self-verified mathematics.** MathGuard extracts equations and
   inequalities directly from the LaTeX ($$...$$) blocks the tutor
   renders, parses \frac{}{}, \sqrt{}, \pi, and other LaTeX constructs,
   and uses sympy to compare the solution set of each step against the
   previous one. Verified via 47 automated tests covering:
   - Deliberately wrong math (adversarial tests)
   - Realistic LaTeX formatting (not idealized plain text)
   - False-positive cases (header text bleeding into a capture, a
     verification/substitution step wrongly compared against a solving
     chain, floating-point rounding on genuinely correct arithmetic)
   - Cross-domain correctness: Trigonometry (degree convention, not
     radians), Finance (symbol collisions with sympy built-ins: I, in),
     Exponents (symbolic identities that are true for all values, not
     "solve for one correct answer" problems), Equations & Inequalities
     (the classic "forgot to flip when dividing by a negative" error),
     Statistics/Measurement (sqrt, pi, decimal-rounding tolerance),
     Analytical Geometry (coordinate-pair notation not colliding with
     the decimal-comma fix)

   Exposed on POST /tutor/message as math_verified (bool) and
   verification_warnings (list[str]), surfaced in the chat UI as a
   visible badge.

   Honest limitation: Euclidean Geometry proof statements (e.g.
   "the diagonals of a parallelogram bisect each other") are not
   equation-shaped, and MathGuard cannot meaningfully verify pure
   logical/geometric reasoning. Geometry problems that reduce to a
   solvable equation (e.g. angle-sum problems) do get real verification;
   pure proofs do not. This is a known, accepted boundary, not a gap
   to be silently papered over.

2. **Root-cause diagnosis before teaching.** The recursive prerequisite
   chain walker runs before the tutor begins explaining, and its
   reasoning is returned via diagnosis_reasoning and surfaced in the UI
   as a distinct message when a redirect happens. All 12 topics have a
   real prerequisite_id link back to Algebra (seeded explicitly -- none
   existed in the original seed data), confirmed live: every topic
   tested correctly identified "no attempt history for Algebra" as a
   possible gap and redirected instruction there before addressing the
   requested topic.

## Topic coverage
All 12 CAPS Grade 10 Pure Mathematics topics are live with real seeded
content, diagnostic questions, and prerequisite links:
Algebra, Exponents, Number Patterns, Equations & Inequalities,
Trigonometry, Functions, Finance & Growth, Statistics, Probability,
Measurement, Euclidean Geometry, Analytical Geometry.

## Consequences
- Both differentiators are demoable across the full curriculum breadth,
  not just the original Algebra pilot -- see docs/DEMO-SCENARIOS.md and
  docs/CAPABILITY-EVIDENCE-LOG.md for concrete, dated evidence of each
  fix.
- Any future topic addition (e.g. Grade 11/12 expansion) should follow
  the same discipline: adversarial + realistic-LaTeX tests before
  seeding content, live-output testing before enabling in the frontend.
  Eight distinct real gaps were found this way across 12 topics -- an
  average of roughly one genuine parsing/verification gap per topic
  that assuming generalization would have missed.
- LLM provider is Anthropic Claude (see ADR-010) -- MathGuard and the
  diagnosis engine are provider-agnostic and unaffected by that choice.

## Update (per later project record, Sept 2026)
MathGuard hardening continued past this ADR to at least nine known
real parsing/verification gaps found via live testing (decimal commas,
`\times` deletion, the imaginary-unit `I` collision, the `in` keyword
collision, inequality direction-flipping, `\sqrt{}`/`\pi` handling,
decimal-rounding tolerance, coordinate-pair notation, and a Unicode
minus-sign case) -- each with its own regression test. Real
authentication (bcrypt password hashing + JWT via python-jose, a
`get_current_learner` dependency) was also added after this ADR,
closing a previously-open "no auth on endpoints" gap. See
REBUILD_SPEC.md for what's known about this later work.
