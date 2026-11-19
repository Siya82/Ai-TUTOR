# ADR-042: Typing fractions, powers and roots in the question box

**Date:** 19 Nov 2026 · **Status:** Accepted (Siya chose option 1 over a MathLive editor)

## Decision
- **Keys:** the symbol keyboard gains structure keys on every topic:
  **a⁄b** inserts `()/()` with the caret in the top box, **xⁿ** inserts
  `^()`, **√** inserts `√()`, and **next ▸** (or **Tab**) jumps to the next
  box, e.g. from a fraction's top to its bottom.
- **Live preview:** "THUTOra will read:" shows the question with real stacked
  fractions, powers and roots (KaTeX, already in the app) as the learner types.
  It appears only when there is a fraction, power or root.
- **What the tutor gets:** `utils/mathInput.js` finds the maths in the sentence
  and sends it as `$LaTeX$` (e.g. "Simplify $\frac{x+1}{x^{2}}-4$ please"), so
  the extent of every fraction is unambiguous. Questions without a fraction,
  power or root are sent exactly as typed. The learner's sent message shows
  as maths in the chat (`MathText`).
- **Assignments:** the answer box shows the same live preview; answers are
  saved as typed (the AI marker reads `(x+1)/(x-2)` correctly, and re-editing
  a saved answer stays plain text).
- No new dependency; ~0 extra data.

## Rules (unit-tested in `__tests__/mathInput.test.js`)
`(a)/(b)` and `a/b` are fractions (spaces around `/` allowed, nesting
allowed); `x^(n)`, `x²` are powers; `√(x)` is a root; unicode symbols map to
LaTeX (≤ θ π Δ …); single letters count as maths only beside an operator, so
"a" in an English sentence stays text; empty boxes show as □.

## Later
If learners struggle with deeply nested expressions, add a MathLive editor for
maths topics only (≈700 KB, so not by default).
