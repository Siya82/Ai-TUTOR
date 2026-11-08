"""
MathGuard: self-verifying mathematics engine. See
docs/ADR-011-protected-differentiators.md -- "a protected core
differentiator", rebuild carefully, re-run the regression suite at
every stage, don't assume.

Core mechanism: extract equations/inequalities directly from the
$$...$$ LaTeX blocks the tutor actually renders (never from plain
prose -- header text bleeding into a capture was a real, fixed bug),
then use sympy (via math_validator.py) to compare each solving step's
solution set against the previous one. The symbol being solved for is
auto-detected per response, never hardcoded to "x".

Honest, permanent limitation: Euclidean Geometry proof statements
(e.g. "the diagonals of a parallelogram bisect each other") are not
equation-shaped and cannot be verified this way -- only geometry
problems that reduce to a solvable equation (angle-sum problems, etc.)
get real verification. This is reflected as an explanatory warning,
not a false "verified" or "failed" claim -- `verified` stays True
whenever no contradiction was actually found, which includes "nothing
here was checkable" as well as "everything checked out".

REBUILD NOTE: rebuilt from REBUILD_SPEC.md Section 1 -- not recovered
code.
"""

import re
from dataclasses import dataclass, field

from app.services.math_validator import (
    build_relation_expr,
    free_symbols_of,
    sets_consistent,
    solve_relation,
    verify_numeric_check,
)

MATH_BLOCK_PATTERN = re.compile(r"\$\$(.+?)\$\$", re.DOTALL)


@dataclass
class MathVerificationResult:
    verified: bool = True
    warnings: list[str] = field(default_factory=list)


def extract_math_blocks(text: str) -> list[str]:
    """Deliberately ONLY $$...$$ delimited blocks -- plain prose, even
    prose that mentions numbers, must never bleed into a capture."""
    return [b.strip() for b in MATH_BLOCK_PATTERN.findall(text)]


def verify_tutor_response(text: str) -> MathVerificationResult:
    """
    Classifies every $$...$$ block in a tutor response as:
    - a "check" step (zero free symbols, e.g. "2(5) + 5 = 15") -- verified
      on its own numerically (gap 3), never chain-compared;
    - a "solving" step (exactly one free symbol) -- chain-compared against
      the previous solving step's solution set;
    - "left unverified" (more than one free symbol -- an identity or
      simplification chain, or a step naming a different variable than
      the rest of the chain) -- not a failure, just honestly not checked.

    `verified` is set False ONLY when a genuine inconsistency is
    positively detected (a check step that doesn't hold numerically, or a
    solving step that doesn't follow from the one before it) -- never
    merely because something couldn't be parsed or judged. That
    distinction is what keeps the "honest limitation" honest: we never
    claim a failure we can't actually demonstrate.
    """
    blocks = extract_math_blocks(text)
    warnings: list[str] = []
    verified = True

    solving_steps: list[tuple[str, object]] = []
    check_steps: list[str] = []

    for block in blocks:
        free_syms, parts = free_symbols_of(block)
        if parts is None:
            warnings.append(f"Could not parse this step for verification: {block[:60]!r}")
            continue
        if len(free_syms) == 0:
            check_steps.append(block)
        elif len(free_syms) == 1:
            solving_steps.append((block, next(iter(free_syms))))
        else:
            warnings.append(
                f"Left unverified (more than one free symbol -- likely an identity or "
                f"simplification, not a single-variable solve): {block[:60]!r}"
            )

    for block in check_steps:
        result = verify_numeric_check(block)
        if result is False:
            warnings.append(f"Substitution/check step does not hold numerically: {block[:60]!r}")
            verified = False
        elif result is None:
            warnings.append(f"Could not numerically verify this check step: {block[:60]!r}")

    symbol_names = {s.name for _, s in solving_steps}
    if len(symbol_names) > 1:
        warnings.append(
            f"Multiple different variables appear across solving steps "
            f"({sorted(symbol_names)}) -- left unverified."
        )
    elif len(solving_steps) >= 2:
        symbol = solving_steps[0][1]
        prev_set = None
        for block, _ in solving_steps:
            rel = build_relation_expr(block, symbol.name)
            sol_set = solve_relation(rel, symbol)
            if prev_set is not None:
                consistency = sets_consistent(prev_set, sol_set)
                if consistency is False:
                    warnings.append(f"This step does not follow from the previous one: {block[:60]!r}")
                    verified = False
                elif consistency is None:
                    warnings.append(f"Could not verify this step against the previous one: {block[:60]!r}")
            prev_set = sol_set

    if not blocks:
        warnings.append(
            "No $$...$$ math blocks found to verify (prose-only response, or a geometry "
            "proof that doesn't reduce to a solvable equation -- see MathGuard's "
            "documented limitation in docs/ADR-011-protected-differentiators.md)."
        )

    return MathVerificationResult(verified=verified, warnings=warnings)
