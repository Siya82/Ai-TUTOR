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


def strip_boxed(s: str) -> str:
    r"""Gap 23 (new, found 15 Nov 2026 via the first live Grade 12
    Differential Calculus test -- exactly the risk ADR-022 flagged as
    untested when Grade 12 content was added): a final boxed answer --
    \boxed{f'(x) = 2x + 3} -- reached sympy's parser as a literal,
    unparseable fragment, the same shape as the strip_text_commands gap
    (gap 14). \boxed{...} is purely presentational -- it never changes
    the mathematical content -- so it is unwrapped (brace-matched, like
    convert_sqrt/convert_frac), keeping everything inside intact rather
    than dropping it the way strip_text_commands drops \text{...}'s
    content."""
    out = []
    i = 0
    pattern = re.compile(r"\\boxed")
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
            out.append(s[j + 1:k - 1])  # keep inner content, drop just \boxed{ and its matching }
            i = k
        else:
            i = j
    return "".join(out)


_PRIME_FUNCTION_CALL = re.compile(r"([a-zA-Z]+)'(\()")


def convert_prime_notation(s: str) -> str:
    """Gap 23 (continued): f'(x)/g'(x)-style derivative notation -- a
    bare apostrophe is not valid syntax anywhere sympy's parser accepts,
    so "f'(x) = 2x + 3" previously failed to parse at all. Renamed
    consistently to a plain, distinct undefined-function name
    ("fprime(x)") -- deliberately NOT related back to f symbolically
    (this project's verification never tracks a function's definition
    across separate steps), just enough to let the actual content of
    the step -- comparing fprime(x) across steps, e.g. against a
    limit evaluation of the same quantity, see
    convert_limit_of_parenthesized_expression below -- be verified like
    any other single-variable step."""
    return _PRIME_FUNCTION_CALL.sub(lambda m: f"{m.group(1)}prime{m.group(2)}", s)


_DECORATIVE_SYMBOLS = re.compile(r"[\u2713\u2714\u2717\u2718\u274c]")  # checkmarks / crosses


def strip_decorative_symbols(s: str) -> str:
    """Gap 13 (found via the step 6 live /tutor/message smoke test): the
    tutor's own calibration anchor asks for a substitution *check* step,
    and a real Claude reply wrote it as "$$15 = 15 \u2713$$" -- a checkmark
    glyph literally inside the $$...$$ block. Left in, sympy reads it as
    a bare one-letter symbol, which then collides with the real solving
    variable (e.g. 'x') and makes the whole chain look like it has
    multiple different variables, leaving a correct check unverified.
    Decorative only -- never part of the actual mathematics -- so it is
    stripped before anything else touches the string."""
    return _DECORATIVE_SYMBOLS.sub("", s)


def normalize_unicode_minus(s: str) -> str:
    """Gap 12: LaTeX/learner input sometimes uses U+2212 rather than ASCII '-'."""
    return s.replace(_UNICODE_MINUS, "-")


# Gap 23 (continued): added a negative lookbehind for a preceding
# backslash -- without it, this pattern also matched a LaTeX
# COMMAND name immediately followed by its own bound-variable
# subscript syntax (e.g. the "lim" in "\lim_{h \to 0}"), misreading it as if it were a plain
# subscripted variable and mangling it beyond recovery before
# convert_limit_of_parenthesized_expression ever saw it. A bare
# variable like "R_{...}" has no preceding backslash and is still
# matched exactly as before.
_BASE_BRACED_SUBSCRIPT = re.compile(r"(?<![\\a-zA-Z])([a-zA-Z]+)_\{")


def convert_braced_subscript(s: str) -> str:
    """Gap 22 (new, found 13 Nov 2026 via the live Electric Circuits stress
    test on a real series-parallel resistor problem): a MULTI-CHARACTER
    LaTeX subscript wrapped in braces -- "R_{\\text{parallel}}",
    "V_{3\\Omega}", "I_{\\text{each}}" -- was never converted into a
    valid sympy identifier at all. A single-character digit subscript
    with no braces (R_1, R_2) already happens to be a legal Python
    identifier as-is and was never a problem; the braced,
    multi-character form is an entirely different case that had no
    handling whatsoever. Worse, it collided badly with gap 14's
    strip_text_commands: because that runs first and unconditionally
    drops a \\text{...} group (including its content) wherever it
    appears, "R_{\\text{parallel}}" -- where the \\text group is NESTED
    one level inside the subscript's own braces, not a top-level unit
    label -- lost its \\text{parallel} entirely but kept the
    subscript's own now-empty braces behind, producing the literal,
    doubly-unparseable "R_{}" (sympy's parser does not accept a bare
    "{" or "}" as syntax at all). Must therefore run BEFORE
    strip_text_commands, doing its own \\text{...}-stripping internally
    as part of building a valid identifier. Converts "BASE_{...}" to
    "BASE_<sanitized>", where <sanitized> keeps only the alphanumeric
    characters from the brace content (backslash commands like \\Omega
    are stripped to their bare name first) -- e.g.
    "R_{\\text{parallel}}" -> "R_parallel", "V_{3\\Omega}" ->
    "V_3Omega". The exact spelling of the generated identifier doesn't
    matter for verification -- only that the SAME LaTeX subscript
    always normalizes to the SAME valid identifier, consistently,
    within and across steps. This is what turned nearly every single
    step of a real worked Electric Circuits reply (34 of the warnings
    returned by one live call) into an unparseable block -- by far the
    most consequential gap found this session."""
    out = []
    i = 0
    while i < len(s):
        m = _BASE_BRACED_SUBSCRIPT.search(s, i)
        if not m:
            out.append(s[i:])
            break
        out.append(s[i:m.start()])
        base = m.group(1)
        j = m.end()  # position right after the subscript's own opening "{"
        depth = 1
        k = j
        while k < len(s) and depth > 0:
            if s[k] == "{":
                depth += 1
            elif s[k] == "}":
                depth -= 1
            k += 1
        inner = s[j:k - 1]
        inner = re.sub(r"\\text\{([^{}]*)\}", r"\1", inner)
        inner = re.sub(r"\\([a-zA-Z]+)", r"\1", inner)
        suffix = re.sub(r"[^0-9a-zA-Z]", "", inner)
        out.append(f"{base}_{suffix}" if suffix else base)
        i = k
    return "".join(out)


def strip_text_commands(s: str) -> str:
    """Gap 14 (found 13 Nov 2026 via the first live Physical Sciences
    smoke test -- not from project memory, a genuinely new finding):
    Maths worked examples never put units inside a $$...$$ block, so
    this was never exercised before. A Physical Sciences reply wrote
    "$$v = 10 \text{ m/s}$$" -- strip_latex_cruft's generic
    backslash-stripping fallback turned "\text{ m/s}" into the literal,
    unparseable "text{ m/s}" (a brace-using fragment that looks like a
    function call but isn't valid syntax), breaking the parse on every
    single numeric-answer line that included a unit. \text{...} is
    never meaningful mathematics -- always a unit label or word
    annotation -- so it (including its content) is dropped entirely,
    same philosophy as strip_decorative_symbols. Brace-matched the same
    way convert_sqrt/convert_frac already are, in case of nested braces."""
    out = []
    i = 0
    pattern = re.compile(r"\\text")
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
            i = k  # drop \text{...} entirely, including its content
        else:
            i = j  # bare \text with no brace group -- just drop the command itself
    return "".join(out)


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


def convert_nth_root(s: str) -> str:
    """Gap 18 (new, found 13 Nov 2026 while scoping Grade 11's Exponents
    and Surds topic): \\sqrt[n]{X} (an indexed/nth root, e.g. a cube
    root) was never handled -- convert_sqrt only matches a \\sqrt that is
    IMMEDIATELY followed by '{', so when it hit the '[' of an index
    instead, its own no-brace fallback branch silently dropped "\\sqrt"
    without emitting anything for it, leaving the bracket-and-braces
    behind as inert text (e.g. "\\sqrt[3]{8}" became the literal,
    unparseable "[3]{8}"). Must run BEFORE convert_sqrt, since a plain
    \\sqrt prefix-match would otherwise still consume (and mishandle) the
    very same text first. Converts to "((X))**(1/(n))", brace-matched
    the same way convert_sqrt/convert_frac already are."""
    out = []
    i = 0
    pattern = re.compile(r"\\sqrt\[(\d+)\]")
    while i < len(s):
        m = pattern.search(s, i)
        if not m:
            out.append(s[i:])
            break
        out.append(s[i:m.start()])
        n = m.group(1)
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
            out.append(f"(({inner}))**(1/({n}))")
            i = k
        else:
            # No brace group after the index -- leave the command alone
            # for convert_sqrt's own (unrelated) fallback rather than guessing.
            out.append(s[m.start():j])
            i = j
    return "".join(out)


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




_LIM_PATTERN = re.compile(r"\\lim_\{\s*([a-zA-Z]+)\s*\\to\s*(-?\d+(?:\.\d+)?)\s*\}")


def convert_limit_of_parenthesized_expression(s: str) -> str:
    r"""Gap 23 (new, found 15 Nov 2026 via the first live Grade 12
    Differential Calculus test -- exactly the risk ADR-022 flagged as
    untested when Grade 12 was added): first-principles differentiation
    writes \lim_{h \to 0}(...) literally, which sympy's parser has no
    native handling for at all. Converts "\lim_{VAR \to VALUE}" plus
    whatever balanced parenthesised expression (optionally with a
    "/(...)" denominator right after it -- convert_frac has already run
    by the time this does, so a \frac{...}{...} that followed a \lim
    has already become exactly this "(...)/(...)" shape) immediately
    follows it into "limit((EXPR), VAR, VALUE)" -- relying on the real
    sympy.limit() function injected into this module's parser locals
    (see _locals()) to actually EVALUATE it during parsing itself, not
    just build an inert symbol.

    Deliberately does nothing special for the case where EXPR still
    contains an undefined function call (e.g. the difference-quotient
    DEFINITION line, \lim_{h \to 0}\frac{f(x+h) - f(x)}{h}, which
    depends on the still-undefined f and can't actually be evaluated
    without knowing f's formula): it is converted the same way as any
    other case, and sympy.limit() is left to either return it
    unevaluated or raise -- both already degrade safely through the
    existing try/except around every sympify_side() call, the same
    honest "left unverified"/"could not parse" territory this block
    would have fallen into before this fix existed. This fix only ever
    ADDS verification coverage for the cases sympy's limit() can
    actually resolve; it never claims a false pass for one it can't.

    MUST run AFTER convert_braced_subscript() in normalize_latex's own
    pipeline -- without that, convert_braced_subscript's own
    "letters immediately followed by _{" pattern would otherwise
    misread "\lim_{h \to 0}" as if "lim" were a plain subscripted
    variable (it is a LaTeX COMMAND, not one), silently mangling it
    into the unparseable "lim_hto0(...)" before this function ever got
    a chance to see the original text. Fixed at the root by giving
    convert_braced_subscript's own pattern a negative lookbehind for a
    preceding backslash (see its own updated comment) rather than by
    reordering around it -- the general bug (ANY "\commandname_{...}"
    LaTeX command, not just \lim, could have been mis-captured the same
    way) is fixed once, not worked around here."""
    out = []
    i = 0
    while i < len(s):
        m = _LIM_PATTERN.search(s, i)
        if not m:
            out.append(s[i:])
            break
        out.append(s[i:m.start()])
        var, value = m.group(1), m.group(2)
        j = m.end()

        def read_paren_group(start):
            depth = 1
            k = start + 1
            while k < len(s) and depth > 0:
                if s[k] == "(":
                    depth += 1
                elif s[k] == ")":
                    depth -= 1
                k += 1
            return s[start:k], k

        if j < len(s) and s[j] == "(":
            group1, k = read_paren_group(j)
            expr = group1
            if k < len(s) and s[k] == "/" and k + 1 < len(s) and s[k + 1] == "(":
                group2, k2 = read_paren_group(k + 1)
                expr = f"{group1}/{group2}"
                k = k2
            out.append(f"limit(({expr}), {var}, {value})")
            i = k
        else:
            # Not immediately followed by a parenthesised expression --
            # leave the \lim command alone; it stays an honest "could
            # not parse" via the normal fallback, same as before this
            # fix existed.
            out.append(s[m.start():j])
            i = j
    return "".join(out)


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


_TRIG_LITERAL_DEGREE = re.compile(r"\\(sin|cos|tan)\(?\s*(\d+(?:\.\d+)?)\s*\u00b0\)?")


def convert_trig_of_literal_degrees(s: str) -> str:
    r"""Gap 16 (found 13 Nov 2026 via live Physical Sciences testing):
    different from gap 4's bare-symbol case (sin(theta), where CAPS
    convention assumes degrees with no literal degree sign written at
    all). A Physical Sciences worked example evaluates a trig function
    AT a known numeric angle, written WITH a literal degree sign and
    often with no parentheses -- "\cos30\u00b0", "\sin 60\u00b0". Observed
    sympy behaviour on this is version-dependent (a parse failure on one
    sympy version, "cos30" silently read as a brand-new unrelated symbol
    on another) because without the parentheses, "cos30" is just one
    token to sympy's tokenizer, not a function call -- so this is
    resolved deterministically via regex, before sympy ever sees the
    string, rather than relying on any particular parser's tokenization.
    Mathematically verified correct: 50*cos(30 deg) ~ 43.301, matching
    the worked example's own 43.3."""
    return _TRIG_LITERAL_DEGREE.sub(lambda m: f"{m.group(1)}(({m.group(2)})*pi/180)", s)


_TRIG_OF_BARE_SYMBOL_NO_PARENS = re.compile(r"\\(sin|cos|tan)\\([a-zA-Z]+)")


def convert_trig_of_bare_symbol_no_parens(s: str) -> str:
    """Gap 20 (new, found 13 Nov 2026 while scoping Grade 11 Physical
    Sciences): "\\cos\\theta" (a trig function applied directly to a
    bare angle SYMBOL, no space and no parentheses) is a real, previously
    seen pattern from this tutor's own live output (the Vectors worked
    example wrote "d\\cos\\theta" this way) -- different from gap 4
    (sin(theta), already has explicit parens) and gap 16 (a literal
    numeric degree value, not a symbol). Left alone, the generic
    backslash-stripping fallback concatenates "\\cos" and "\\theta" with
    nothing between them into the single nonsense token "costheta",
    which sympy's implicit-multiplication parser then shatters into one
    bogus single-letter symbol per character (c, o, s, t, h, e, t, a).
    Converts to "cos(theta)" before that fallback ever runs. Explicitly
    does NOT match when the following command is "left"/"right" (e.g.
    "\\cos\\left(\\theta\\right)"), which is real LaTeX sizing syntax
    around an already-explicit paren, not a bare angle name -- left
    alone so strip_latex_cruft's existing \\left/\\right handling (and the
    real parens already present) can do their normal job instead.
    Deliberately does NOT touch "\\cos \\theta" (WITH a space) -- that
    case already parses correctly today via sympy's own
    implicit_multiplication_application transformation, which recognizes
    a known function name followed by a space-separated argument as a
    function call, not a product."""
    def repl(m):
        func, name = m.group(1), m.group(2)
        if name in ("left", "right"):
            return m.group(0)
        return f"{func}({name})"
    return _TRIG_OF_BARE_SYMBOL_NO_PARENS.sub(repl, s)


_LETTER_ADJACENT_TRIG_CALL = re.compile(r"(?<!arc)(?<=[a-zA-Z])(sin|cos|tan)\(")


def insert_multiplication_before_adjacent_trig_call(s: str) -> str:
    """Gap 21 (new, found 13 Nov 2026 alongside gap 20, same Grade 11
    Physical Sciences scoping pass): once a trig command has been
    converted to an actual function call -- "cos(...)" -- by gap 16
    (literal degree) or gap 20 (bare symbol, no parens) above, a letter
    glued directly against it with no space or operator (e.g. the "d"
    in "d\\cos\\theta", or the "BA" in a flux formula "BA\\cos\\theta")
    is FAR worse than the naming-collision risk gap 13/20 already guard
    against: sympy's implicit-multiplication parser doesn't just misname
    the result, it drops the trig call ENTIRELY and shatters the whole
    run into single-letter symbols multiplied together ("dcos(theta)"
    parses as "c*d*o*s*theta", with no cos() anywhere in the result).
    A single digit immediately before a trig call ("2cos(theta)") does
    NOT need this -- sympy's own implicit_multiplication_application
    already handles a leading digit correctly; only a LETTER directly
    before "sin("/"cos("/"tan(" is the broken case. Explicitly excludes
    "arccos(" (and arcsin/arctan) via a fixed-width negative lookbehind,
    since that would otherwise be misread as "arc" times "cos(...)" --
    this project doesn't currently use inverse trig notation at all, but
    there's no reason to silently break it if that ever changes."""
    return _LETTER_ADJACENT_TRIG_CALL.sub(r"*\1(", s)


def strip_bare_degree_sign(s: str) -> str:
    """Gap 16 (continued): runs AFTER convert_trig_of_literal_degrees has
    already consumed every degree sign that was actually part of a trig
    argument -- any degree sign still remaining at this point is just
    decorative, on a final numeric angle answer (e.g. "theta = 30\u00b0"),
    same role as a unit label. Dropping it is correct and consistent
    with gap 4's own convention that a bare angle NUMBER (no radian
    conversion applied) is understood to already be in degrees."""
    return s.replace("\u00b0", "")


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
    s = strip_boxed(s)
    s = convert_prime_notation(s)
    s = strip_decorative_symbols(s)
    s = convert_braced_subscript(s)  # gap 22 -- must run before strip_text_commands
    s = strip_text_commands(s)  # gap 14 -- before anything else touches units
    s = normalize_unicode_minus(s)
    s = normalize_decimal_commas(s)
    s = convert_relation_operators(s)  # gap 15 -- must run before strip_latex_cruft
    s = convert_times(s)
    s = convert_trig_of_literal_degrees(s)  # gap 16 -- must run before strip_latex_cruft
    s = convert_trig_of_bare_symbol_no_parens(s)  # gap 20 -- also before strip_latex_cruft
    s = insert_multiplication_before_adjacent_trig_call(s)  # gap 21 -- after gaps 16/20 produce cos(...) calls
    s = convert_frac(s)
    s = convert_nth_root(s)  # gap 18 -- must run before convert_sqrt
    s = convert_sqrt(s)
    s = convert_pi(s)
    s = convert_power(s)
    s = convert_limit_of_parenthesized_expression(s)
    s = strip_latex_cruft(s)
    s = strip_bare_degree_sign(s)  # gap 16 continued -- after trig conversion consumed the real ones
    s = protect_in_keyword(s)
    return s.strip()


# Gap 15 (found 13 Nov 2026 alongside gap 14): these backslash-form
# patterns were DEAD CODE -- normalize_latex's strip_latex_cruft step
# already strips every backslash-letter command (via its generic
# fallback) BEFORE split_relation ever runs on the result, so "\leq"
# had already become the bare word "leq" with no backslash left to
# match against "\\leq" below. Never caught before because every existing
# regression test for inequalities used plain ASCII (-2x > 6), never the
# LaTeX relation form Claude actually renders. Fixed properly in
# normalize_latex via convert_relation_operators(), which runs BEFORE
# strip_latex_cruft -- these patterns are kept only as a documented,
# harmless no-op fallback.  \approx is new: a Physical Sciences
# "rounds to" check step (e.g. "$$d = \sqrt{2499.9} \approx 50$$"),
# treated as equality for verification purposes (NUMERIC_TOLERANCE/
# CHAIN_RELATIVE_TOLERANCE already express the right amount of "approximately").
_REL_OPERATORS = [
    (r"\\neq", "!="), (r"\\leq", "<="), (r"\\geq", ">="),
    (r"\\le", "<="), (r"\\ge", ">="),
    ("<=", "<="), (">=", ">="), ("!=", "!="),
    ("=", "="), ("<", "<"), (">", ">"),
]

_LATEX_RELATION_CONVERSIONS = [
    (r"\\leq", "<="), (r"\\geq", ">="), (r"\\neq", "!="), (r"\\approx", "="),
    (r"\\le\b", "<="), (r"\\ge\b", ">="),
]


def convert_relation_operators(s: str) -> str:
    """Gap 15: converts LaTeX relation commands to their ASCII
    equivalents BEFORE strip_latex_cruft can strip their backslash and
    turn them into unmatched plain words. Order matters -- the 4-letter
    forms (leq/geq/neq/approx) must convert before the 2-letter le/ge
    forms, or a leftover "q" would be stranded."""
    for pat, repl in _LATEX_RELATION_CONVERSIONS:
        s = re.sub(pat, repl, s)
    return s


_ALL_REL_OP_PATTERNS = [pat for pat, _ in _REL_OPERATORS]


def _contains_relation_operator(s: str) -> bool:
    """Gap 19 helper: true if ANY relational-operator pattern still
    appears in s. Safe as a plain substring/regex scan -- in this
    domain, <, >, =, <=, >=, != never appear for any reason other than
    marking a relation, so finding one left over in what's supposed to
    be a single side means the block wasn't actually one relation."""
    return any(re.search(pat, s) for pat in _ALL_REL_OP_PATTERNS)


def split_relation(normalized: str) -> tuple[str, str, str] | None:
    """Finds the first top-level relational operator and splits on it.

    Gap 19 (new, found 13 Nov 2026 while scoping Grade 11's quadratic
    inequalities, e.g. "x < -2 \\text{ or } x > 3"): once gap 14 strips
    "\\text{ or }" entirely, a compound/union answer like that collapses
    to "x < -2  x > 3" -- two relations with nothing left connecting
    them. The naive first-operator split used to hand "-2  x > 3" to
    sympy as a RHS; sympy's parser doesn't reject that, it happily
    parses it AS ITS OWN relational expression (an inequality), which
    then crashed downstream code (build_relation_expr's "l < r") with a
    raw TypeError the moment it tried to compare that relational object
    as if it were a plain numeric expression -- a real crash risk for
    the live /tutor/message endpoint, not just a lost verification. Now
    explicitly detected and rejected here: if either side still
    contains another relational operator after the split, this isn't
    one relation at all, so it's treated exactly like any other
    unparseable block (returns None) -- an honest "left unverified" via
    the normal path, never a crash. Compound/union inequality ANSWERS
    are consequently a known, accepted, new "unverified" case, the same
    category as a multi-symbol identity -- not something this fix
    claims to actually verify."""
    for pat, op in _REL_OPERATORS:
        m = re.search(pat, normalized)
        if m:
            lhs, rhs = normalized[:m.start()].strip(), normalized[m.end():].strip()
            if _contains_relation_operator(lhs) or _contains_relation_operator(rhs):
                return None
            return lhs, op, rhs
    return None


def _locals() -> dict:
    d = {name: Symbol(name) for name in RESERVED_SYMBOL_NAMES}
    # Gap 23: lets a converted "limit((EXPR), VAR, VALUE)" call (built by
    # convert_limit_of_parenthesized_expression() from a \lim_{...}(...)
    # block) actually CALL sympy's real limit() function at parse time,
    # rather than being read as a literal, undefined function named
    # "limit".
    d["limit"] = sympy.limit
    return d


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


# Gap 17 (found 13 Nov 2026 via live Physical Sciences testing): CAPS
# Physical Sciences convention is to round intermediate trig/arithmetic
# results to 3-4 significant figures and carry the ROUNDED value
# forward into the next step (e.g. "cos30 degrees ~ 0.866" then
# "50 * 0.866 = 43.3"), unlike Maths, which never has this kind of
# expected per-step rounding. NUMERIC_TOLERANCE (1e-6, flat/absolute)
# is exactly right for Maths's exact arithmetic but too strict for
# this -- it was flagging pedagogically correct, properly-rounded
# Physics steps as "does not follow from the previous one" purely
# because 50*cos(30deg)=43.30127... differs from 50*0.866=43.3 by
# ~0.0013, which exceeds 1e-6 in absolute terms even though it is a
# normal, expected rounding difference, not a mathematical error.
# CHAIN_RELATIVE_TOLERANCE is deliberately separate from
# NUMERIC_TOLERANCE (not a change to the global constant) so Maths's
# existing exact-arithmetic guarantee (gap 5c: x=2 vs x=7 must still be
# flagged) is completely unaffected -- it only widens the chain
# consistency check specifically, nowhere near loose enough to mask a
# genuine conceptual/arithmetic error (0.1% relative vs. gap 5c's ~250%
# relative discrepancy).
CHAIN_RELATIVE_TOLERANCE = 1e-3


def is_numeric_subset(later_floats: list[float], earlier_floats: list[float],
                       tol: float = NUMERIC_TOLERANCE,
                       rel_tol: float = CHAIN_RELATIVE_TOLERANCE) -> bool:
    """
    Gap 5: every value in `later` must be numerically close (not exactly
    equal -- sympy's Float(20.0) == Integer(20) is False even though they
    are the same number) to SOME value in `earlier`. A later step may
    validly narrow to fewer solutions (e.g. discarding an extraneous root
    after squaring) without being flagged.

    Gap 17: the per-pair tolerance is the LARGER of the flat absolute
    tolerance and a tolerance relative to the earlier value's magnitude
    -- see CHAIN_RELATIVE_TOLERANCE's own comment for why.
    """
    for lf in later_floats:
        if not any(abs(lf - ef) <= max(tol, rel_tol * max(1, abs(ef))) for ef in earlier_floats):
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
