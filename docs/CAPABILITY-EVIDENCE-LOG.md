
### 2026-08-26 -- MathGuard upgraded from syntax-check to real correctness verification
**Capability:** Self-verified mathematics
**What happened:** Discovered MathGuard originally only validated that
equations were well-formed (parseable), not that each step actually
followed from the previous one -- a 0/3 catch rate on deliberately wrong
math proved this. Rebuilt equation extraction to read directly from the
LaTeX ($$...$$) blocks the tutor actually renders, added real solution-set
comparison between consecutive steps (via existing but unused
equations_are_equivalent_step in math_validator.py), and fixed a false
positive risk where step-header text (e.g. "## Step 1: Subtract 5...")
could bleed into an equation capture. Final catch rate: 3/3 on adversarial
wrong-math tests, correctly silent on genuinely correct math, correctly
handles chained equality checks ("2(5)+5 = 10+5 = 15").
**Why it matters:** This is the concrete mechanism behind "verifies its
own math" -- not a claim, a tested, reproducible behavior. See
tests/test_math_guard_adversarial.py, tests/test_math_guard_latex.py,
tests/test_math_guard_header_bleed.py.

### 2026-08-26 -- MathGuard upgraded from syntax-check to real correctness verification (revised)
**Capability:** Self-verified mathematics
**What happened:** Initial fix (comparing solution sets between consecutive
LaTeX-extracted equations) caught real wrong math but also produced false
positives on genuinely correct responses: a \frac{}{} construct failed to
parse, a stray markdown "**" bled into an equation capture, and a
"check your answer" substitution step was wrongly compared against the
solving chain as if it were a continuation of it. Fixed by parsing \frac,
stripping markdown artifacts, and using sympy's actual free_symbols (not
a naive \bx\b regex, which fails on "2x" since digit-letter isn't a word
boundary) to only chain-compare equations that still involve the solve
variable. Final state: 9/9 tests passing, including two independent live
Claude generations with zero false positives and zero missed errors.
**Why it matters:** The false-positive-then-fix cycle is itself evidence
worth keeping -- it shows the verification layer was tested against
adversarial AND real-world content, not just tuned to pass a demo once.

### 2026-08-26 -- MathGuard generalized beyond Algebra's variable 'x'
**Capability:** Self-verified mathematics (now topic-general)
**What happened:** Refactored MathGuard to classify each extracted
equation (numeric / single-unknown / unverifiable) and auto-detect
whichever symbol is actually being solved for, rather than hardcoding
'x'. This makes the existing verification mechanism apply correctly to
Trigonometry (theta), Finance & Growth (A, P, r, n), and any future
topic with a different variable convention, without further changes.
Equations involving multiple free symbols (algebraic identities,
simplification chains) are explicitly left unverified rather than
guessed at -- planned as a separate, future addition once we're
building topics that need it (Trigonometry identities, Exponent laws),
with its own adversarial test suite the same way this was built.
Caught and fixed a subtle test bug in the process: an earlier adversarial
test using plain prose ("Solve 2x+5=15:") let header text bleed into an
equation capture, producing a false catch for the wrong reason. Rewrote
using realistic $$-wrapped LaTeX, matching actual tutor output.
**Why it matters:** This is the foundation for extending working topics
beyond Algebra (Trigonometry, Functions, Finance & Growth) without
silently losing verification coverage on the way.

### 2026-08-26 -- MathGuard verified across Trigonometry and Finance & Growth
**Capability:** Self-verified mathematics (cross-domain proof)
**What happened:** Wrote adversarial tests for Trigonometry (sin/theta)
and Finance & Growth (simple interest, solving for principal), which
immediately surfaced two real gaps the Algebra-only testing hadn't
exposed: (1) sympy's trig functions assume radians, but CAPS teaches
degrees, so a correct "theta = 30" step was wrongly flagged against
sin(theta)=0.5; (2) floating-point rounding (1100/1.1 not landing on
exactly 1000.0) caused a false inconsistency flag on genuinely correct
finance arithmetic. Fixed both: added degree-convention handling for
direct trig-of-variable expressions, and replaced strict solution-set
equality with tolerance-based numeric comparison plus subset semantics
(a later step may validly narrow to fewer solutions -- e.g. one angle,
one relevant root -- without being flagged, so long as nothing
extraneous is introduced). 16/16 tests passing across Algebra,
Trigonometry, and Finance & Growth, plus a cross-contamination test
confirming a response mixing multiple variables doesn't corrupt either
chain's verification.
**Why it matters:** This is the concrete proof that MathGuard's
verification generalizes beyond the original Algebra pilot -- not
assumed, tested against deliberately wrong math in each new domain.

### 2026-08-26 -- Fixed three real parsing gaps found by testing Finance & Growth live
**Capability:** Self-verified mathematics (parsing robustness)
**What happened:** Testing the newly-seeded Finance & Growth topic against
a real Claude response (simple interest calculation) surfaced three
distinct, genuine parsing gaps that Algebra/Trigonometry testing hadn't
exposed: (1) South African/European decimal comma notation
(LaTeX's 0{,}05 idiom) wasn't normalized to a period before parsing;
(2) \times (LaTeX multiplication) was being deleted rather than
converted to *, leaving two numbers separated by only whitespace,
which sympy can't safely read as multiplication; (3) the variable "I"
(conventionally used for Interest) collided with sympy's built-in
imaginary unit constant, silently causing every equation using it to
be misread. All three fixed at the parsing layer (universal, not
topic-specific -- these could affect any topic's LaTeX output, and the
symbol-collision fix protects against I, E, S, N, O, Q colliding with
sympy built-ins in any future topic too). 18/18 tests passing, including
regression tests for both the comma-decimal and multiplication-symbol
cases.
**Why it matters:** Confirms the "test each topic against real live
output before enabling it" step of the roadmap is doing real work --
these were not hypothetical edge cases, they were the actual first
real Finance response produced.

### 2026-08-26 -- All 12 CAPS Grade 10 Pure Maths topics now live
**Capability:** Full curriculum coverage with tested verification
**What happened:** Extended from Algebra-only to all 12 topics in the
CAPS Grade 10 Pure Mathematics panel: Algebra, Exponents, Number
Patterns, Equations & Inequalities, Trigonometry, Functions, Finance &
Growth, Statistics, Probability, Measurement, Euclidean Geometry, and
Analytical Geometry. Each topic was tested against both deterministic
adversarial cases AND real live Claude output before being enabled --
not assumed to work by extension of earlier topics. This process found
and fixed real gaps specific to several domains: inequality direction-
flipping (the classic "forgot to flip when dividing by a negative"
error), sqrt/pi/decimal-tolerance for Statistics and Measurement, and
a coordinate-pair notation collision with the earlier decimal-comma fix
that would have silently corrupted Analytical Geometry midpoint/
distance answers. Euclidean Geometry is seeded and diagnosis-capable,
but its verification coverage is honestly partial: pure proof
statements (e.g. "diagonals of a parallelogram bisect each other")
aren't equation-shaped and MathGuard can't meaningfully check them --
only geometry problems that reduce to solvable equations (like angle-
sum problems) get real verification.
**Why it matters:** This is full breadth achieved without sacrificing
the depth-first discipline the project is built on -- every topic has
real seeded content, a real prerequisite link to Algebra, and a
documented, tested verification story (including its honest limits).

<!-- Entries after this point (per later project memory, not transcribed
verbatim here since the source file wasn't re-read in full) include at
least three further MathGuard gaps: the 'in' keyword collision, a
Unicode minus-sign case, and decimal-rounding tolerance refinements --
bringing the known total to at least nine real gaps found via live
testing. See REBUILD_SPEC.md. -->
