"""
Low-level LaTeX normalization and sympy parsing/solving for MathGuard.
See docs/ADR-011-protected-differentiators.md and REBUILD_SPEC.md
Section 1 (the 12 numbered, individually-fixed parsing/verification
gaps) -- this module exists specifically to re-implement those 12.

REBUILD NOTE: rebuilt from REBUILD_SPEC.md Section 1 -- the exact
original implementation was never recovered verbatim. Every one of the
12 documented gaps was reproduced with a failing case first and then
fixed here; see tests/test_math_validator.py for one regression test
per gap, numbered to match REBUILD_SPEC.md's own numbering.
"""

import re

import sympy
from sympy import Eq, Symbol
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)

# Gap 8: letters that collide with sympy builtins (I = imaginary unit, E =
# Euler's number, S/N/O/Q = sympy registries/singletons) but are
# conventionally plain algebra variables in CAPS problems (I for Interest
# in Finance, in particular). Forced to plain Symbols via a locals dict
# rather than text surgery, so e.g. "I" still reads as "I" everywhere.
RESERVED_SYMBOL_NAMES = ["I", "E", "S", "N", "O", "Q"]

NUMERIC_TOLERANCE = 1e-6  # gap 5: float-precision tolerance, not exact equality

_UNICODE_MINUS = "\u2212"  # gap 12

_TRANSFORMATIONS = standard_transformations + (
    implicit_multiplication_application,  # lets "2x" parse as 2*x
    convert_xor,
)


def strip_markdown_artifacts(s: str) -> str:
    """Gap 2: stray bold markers (**) bleeding into an equation capture."""
    return s.replace("**", "").replace("__", "")


def normalize_unicode_minus(s: str) -> str:
    """Gap 12: LaTeX/learner input sometimes uses U+2212 rather than ASCII '-'."""
    return s.replace(_UNICODE_MINUS, "-")


def normalize_decimal_commas(s: str) -> str:
    """
    Gap 6 (and the gap-11 interaction with it): the SA/European decimal-comma
    idiom in LaTeX is specifically BRACED -- 0{,}05 -- never a bare comma.
    This regex only touches a comma wrapped in braces between two digits, so
    a bare coordinate-pair comma like in (2,3) is never touched at all (gap
    11 is resolved by this scoping, not by a separate special case).
    """
    return re.sub(r"(?<=\d)\{,\}(?=\d)", ".", s)


def convert_times(s: str) -> str:
    """Gap 7: \\times must become '*', not be deleted (deleting it leaves two
    numbers separated only by whitespace, which can't be parsed as a product)."""
    return re.sub(r"\\times", "*", s)


def convert_sqrt(s: str) -> str:
    """Gap 10: \\sqrt{X} -> sqrt((X)), handling nested braces."""
    out = []
    i = 0
    pattern = re.compile(r"\\sqrt")
    while i < len(s):
        m = pattern.search(s, i)
        if not m:
            out.append(s[i:])
            break
        out.append(s[i:m.start()])
        j = m.end()
        if j < len(s) and s[j] == "{":
            depth = 1
            k = j + 1
            while k < len(s) and depth > 0:
                if s[k] == "{":
                    depth += 1
                elif s[k] == "}":
                    depth -= 1
                k += 1
            inner = s[j + 1:k - 1]
            out.append(f"sqrt(({inner}))")
            i = k
        else:
            i = j
    return "".join(out)


def convert_pi(s: str) -> str:
    """Gap 10: \\pi -> pi (sympy's parser resolves the bare name "pi" to its builtin)."""
    return re.sub(r"\\pi", "pi", s)


def convert_frac(s: str) -> str:
    """Gap 1: \\frac{A}{B} -> ((A))/((B)), recursively (handles nested fractions)."""
    pattern = re.compile(r"\\frac")
    while True:
        m = pattern.search(s)
        if not m:
            return s
        j = m.end()
        if j >= len(s) or s[j] != "{":
            s = s[:m.start()] + s[j:]
            continue

        def read_brace_group(start):
            depth = 1
            k = start + 1
            while k < len(s) and depth > 0:
                if s[k] == "{":
                    depth += 1
                elif s[k] == "}":
                    depth -= 1
                k += 1
            return s[start + 1:k - 1], k

        numer, k1 = read_brace_group(j)
        if k1 >= len(s) or s[k1] != "{":
            s = s[:m.start()] + f"(({numer}))" + s[k1:]
            continue
        denom, k2 = read_brace_group(k1)
        s = s[:m.start()] + f"(({numer}))/(({denom}))" + s[k2:]


def convert_power(s: str) -> str:
    """x^{2} -> x**(2) ; x^2 -> x**2 -- not one of the 12 numbered gaps, but
    needed for any \\frac/plain exponent to reach sympy's parser at all."""
    s = re.sub(r"\^\{([^{}]*)\}", r"**(\1)", s)
    s = re.sub(r"\^(\w)", r"**\1", s)
    return s


def strip_latex_cruft(s: str) -> str:
    s = s.replace("\\left", "").replace("\\right", "")
    s = s.replace("\\,", " ").replace("\\!", "")
    s = s.replace("$$", "").replace("$", "")
    # Generic fallback for any remaining backslash-prefixed LaTeX command made
    # of plain letters (trig functions like \sin/\cos/\tan, Greek-letter
    # variable names like \theta/\alpha) -- runs LAST, after the specific
    # \frac / \sqrt / \pi / \times conversions above have already consumed
    # the commands that need special (not just backslash-stripping) handling.
    s = re.sub(r"\\([a-zA-Z]+)", r"\1", s)
    return s


def protect_in_keyword(s: str) -> str:
    """Gap 8 (continued): "in" is a Python keyword, so it can't appear as a
    bare variable name in the string sympy's parser evaluates -- rename it."""
    return re.sub(r"\bin\b", "in_var", s)


def apply_degree_conversion_for_bare_trig(s: str, symbol_name: str) -> str:
    """
    Gap 4: sympy's trig functions default to radians; CAPS teaches degrees.
    Scoped deliberately to the DIRECT trig-of-a-bare-variable case only
    (sin(theta), not sin(2*theta) or sin(theta + 10)), matching
    REBUILD_SPEC.md's own documented scope for this fix.
    """
    pattern = re.compile(r"\b(sin|cos|tan)\(\s*" + re.escape(symbol_name) + r"\s*\)")
    return pattern.sub(lambda m: f"{m.group(1)}({symbol_name}*pi/180)", s)


def normalize_latex(raw: str) -> str:
    """Runs every normalization fix, in an order where each stage's output
    is valid input for the next (e.g. \\frac is converted before the
    generic backslash-stripping fallback would otherwise mangle it)."""
    s = raw
    s = strip_markdown_artifacts(s)
    s = normalize_unicode_minus(s)
    s = normalize_decimal_commas(s)
    s = convert_times(s)
    s = convert_frac(s)
    s = convert_sqrt(s)
    s = convert_pi(s)
    s = convert_power(s)
    s = strip_latex_cruft(s)
    s = protect_in_keyword(s)
    return s.strip()


_REL_OPERATORS = [
    (r"\\neq", "!="), (r"\\leq", "<="), (r"\\geq", ">="),
    (r"\\le", "<="), (r"\\ge", ">="),
    ("<=", "<="), (">=", ">="), ("!=", "!="),
    ("=", "="), ("<", "<"), (">", ">"),
]


def split_relation(normalized: str) -> tuple[str, str, str] | None:
    """Finds the first top-level relational operator and splits on it."""
    for pat, op in _REL_OPERATORS:
        m = re.search(pat, normalized)
        if m:
            return normalized[:m.start()].strip(), op, normalized[m.end():].strip()
    return None


def _locals() -> dict:
    return {name: Symbol(name) for name in RESERVED_SYMBOL_NAMES}


def sympify_side(expr_str: str):
    return parse_expr(expr_str, local_dict=_locals(), transformations=_TRANSFORMATIONS)


def free_symbols_of(latex_block: str) -> tuple[set, tuple[str, str, str] | None]:
    """
    Returns (free_symbols, (lhs, op, rhs)) on a successful parse -- note
    free_symbols can legitimately be an EMPTY set for a pure-number
    "check your answer" step (gap 3) -- or (set(), None) if the block
    could not be parsed at all.
    """
    normalized = normalize_latex(latex_block)
    parts = split_relation(normalized)
    if not parts:
        return set(), None
    lhs, op, rhs = parts
    try:
        l = sympify_side(lhs)
        r = sympify_side(rhs)
    except Exception:
        return set(), None
    return (l.free_symbols | r.free_symbols), (lhs, op, rhs)


def build_relation_expr(latex_block: str, solving_symbol_name: str | None):
    """Builds the sympy relational (Eq/Lt/Gt/Le/Ge/Ne) for one step, applying
    the degree conversion first when a solving symbol is given."""
    normalized = normalize_latex(latex_block)
    if solving_symbol_name:
        normalized = apply_degree_conversion_for_bare_trig(normalized, solving_symbol_name)
    parts = split_relation(normalized)
    if not parts:
        return None
    lhs, op, rhs = parts
    l = sympify_side(lhs)
    r = sympify_side(rhs)
    if op == "=":
        return Eq(l, r)
    if op == "!=":
        return sympy.Ne(l, r)
    if op == "<=":
        return l <= r
    if op == ">=":
        return l >= r
    if op == "<":
        return l < r
    if op == ">":
        return l > r
    return None


def solve_relation(rel, symbol):
    """
    Returns a sympy set (FiniteSet, Interval, Union, EmptySet, ...), or
    None if solving failed.

    Equations use sympy.solve() rather than solveset(): for periodic
    equations (trig) solveset's full solution set is an infinite
    ImageSet, which is mathematically correct but not what a CAPS-level
    learner is expected to produce (they give the finite, principal
    solutions -- e.g. theta = 30 or 150 for sin(theta) = 0.5, not
    "theta = 30 + 360n for all integers n"). solve() gives exactly that
    finite, learner-shaped answer. Inequalities keep using solveset,
    since Interval/Union containment is exactly right for them and
    doesn't have this periodicity issue (gap 9).
    """
    if isinstance(rel, Eq):
        try:
            raw_solutions = sympy.solve(rel, symbol)
        except Exception:
            return None
        real_solutions = []
        for sol in raw_solutions:
            try:
                value = complex(sympy.N(sol))
            except Exception:
                return None
            if abs(value.imag) > NUMERIC_TOLERANCE:
                continue  # drop non-real roots -- CAPS Grade 10 verification is real-only
            real_solutions.append(value.real)
        return sympy.FiniteSet(*real_solutions) if real_solutions else sympy.EmptySet
    try:
        return sympy.solveset(rel, symbol, domain=sympy.S.Reals)
    except Exception:
        return None


def finite_real_floats(sol_set) -> list[float] | None:
    """FiniteSet of real numbers -> plain Python floats, or None if sol_set
    isn't a FiniteSet, or contains a non-real element."""
    if not isinstance(sol_set, sympy.FiniteSet):
        return None
    out = []
    for el in sol_set:
        try:
            v = complex(el.evalf())
        except Exception:
            return None
        if abs(v.imag) > NUMERIC_TOLERANCE:
            return None
        out.append(v.real)
    return out


def is_numeric_subset(later_floats: list[float], earlier_floats: list[float],
                       tol: float = NUMERIC_TOLERANCE) -> bool:
    """
    Gap 5: every value in `later` must be numerically close (not exactly
    equal -- sympy's Float(20.0) == Integer(20) is False even though they
    are the same number) to SOME value in `earlier`. A later step may
    validly narrow to fewer solutions (e.g. discarding an extraneous root
    after squaring) without being flagged.
    """
    for lf in later_floats:
        if not any(abs(lf - ef) <= tol for ef in earlier_floats):
            return False
    return True


def sets_consistent(earlier_set, later_set) -> bool | None:
    """
    True if later_set is an acceptable narrowing/continuation of
    earlier_set; False if later_set contains something earlier_set does
    not support (gap 9's inequality direction-flip shows up here as a
    direct False, since each side is solved independently from what's
    literally written -- a wrongly-"corrected" direction just won't be a
    subset of the real answer); None if the sets aren't in a form this
    can judge, which callers must treat as "leave unverified", not as a
    failure.
    """
    if earlier_set is None or later_set is None:
        return None

    if isinstance(earlier_set, sympy.FiniteSet) and isinstance(later_set, sympy.FiniteSet):
        earlier_floats = finite_real_floats(earlier_set)
        later_floats = finite_real_floats(later_set)
        if earlier_floats is None or later_floats is None:
            return None
        return is_numeric_subset(later_floats, earlier_floats)

    try:
        result = later_set.is_subset(earlier_set)
        return None if result is None else bool(result)
    except Exception:
        return None


def verify_numeric_check(block: str) -> bool | None:
    """
    Verifies a "check your answer" / substitution step (gap 3) -- a block
    with ZERO free symbols, like 2(5) + 5 = 15 -- on its OWN, numerically,
    rather than chain-comparing it against the solving sequence's
    solution sets (which is the bug this gap describes: a pure-number
    check isn't a continuation of the solving chain and was being wrongly
    compared as if it were one).
    """
    normalized = normalize_latex(block)
    parts = split_relation(normalized)
    if not parts:
        return None
    lhs, op, rhs = parts
    try:
        l = complex(sympify_side(lhs).evalf())
        r = complex(sympify_side(rhs).evalf())
    except Exception:
        return None
    if abs(l.imag) > NUMERIC_TOLERANCE or abs(r.imag) > NUMERIC_TOLERANCE:
        return None
    lf, rf = l.real, r.real
    tol = NUMERIC_TOLERANCE * max(1, abs(lf), abs(rf))
    if op == "=":
        return abs(lf - rf) <= tol
    if op == "!=":
        return abs(lf - rf) > tol
    if op == "<=":
        return lf <= rf + tol
    if op == ">=":
        return lf >= rf - tol
    if op == "<":
        return lf < rf
    if op == ">":
        return lf > rf
    return None
