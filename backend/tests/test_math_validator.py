"""
One regression test per numbered gap in REBUILD_SPEC.md Section 1's
MathGuard section (and ADR-011) -- each of these reproduces a specific,
previously real, documented bug. Pure -- no DB, no network, no sympy
Internet access needed.
"""

import sympy
from sympy import Symbol

from app.services.math_validator import (
    build_relation_expr,
    finite_real_floats,
    free_symbols_of,
    is_numeric_subset,
    normalize_latex,
    sets_consistent,
    solve_relation,
    split_relation,
)

x = Symbol("x")
theta = Symbol("theta")


def _finite_eq(sol_set, expected) -> bool:
    floats = finite_real_floats(sol_set)
    return floats is not None and sorted(floats) == sorted(float(e) for e in expected)


def test_gap1_frac_parsing():
    rel = build_relation_expr(r"\frac{2x+4}{2} = 5", "x")
    assert _finite_eq(solve_relation(rel, x), {3})


def test_gap2_markdown_artifacts_stripped():
    rel = build_relation_expr(r"**2x = 10**", "x")
    assert _finite_eq(solve_relation(rel, x), {5})


def test_gap3_check_step_is_not_chain_compared():
    # A check/substitution step (zero free symbols) is handled by
    # math_guard.verify_numeric_check, not this module's chain logic --
    # see test_math_guard.py for the full-response version of this gap.
    rel = build_relation_expr(r"2(5) + 5 = 15", None)
    assert rel.free_symbols == set()


def test_gap4_degree_not_radian_convention():
    rel1 = build_relation_expr(r"\sin(\theta) = 0.5", "theta")
    sol1 = solve_relation(rel1, theta)
    rel2 = build_relation_expr(r"\theta = 30", "theta")
    sol2 = solve_relation(rel2, theta)
    assert sets_consistent(sol1, sol2) is True


def test_gap5a_float_tolerance_not_exact_equality():
    rel1 = build_relation_expr(r"1.1x = 1100", "x")
    rel2 = build_relation_expr(r"x = 1000", "x")
    assert sets_consistent(solve_relation(rel1, x), solve_relation(rel2, x)) is True


def test_gap5b_narrowing_to_fewer_solutions_is_allowed():
    rel1 = build_relation_expr(r"x^{2} = 4", "x")
    rel2 = build_relation_expr(r"x = 2", "x")
    assert sets_consistent(solve_relation(rel1, x), solve_relation(rel2, x)) is True


def test_gap5c_a_genuinely_wrong_step_is_still_flagged():
    rel1 = build_relation_expr(r"x = 2", "x")
    rel2 = build_relation_expr(r"x = 7", "x")
    assert sets_consistent(solve_relation(rel1, x), solve_relation(rel2, x)) is False


def test_gap6_decimal_comma_normalization():
    rel = build_relation_expr(r"0{,}05*x = 1", "x")
    assert _finite_eq(solve_relation(rel, x), {20})


def test_gap7_times_converted_not_deleted():
    rel = build_relation_expr(r"5 \times x = 20", "x")
    assert _finite_eq(solve_relation(rel, x), {4})


def test_gap8a_reserved_symbol_collision():
    I = Symbol("I")
    rel = build_relation_expr(r"I = 100 * 0.05 * 2", None)
    assert rel.lhs == I


def test_gap8b_in_keyword_collision():
    rel = build_relation_expr(r"in + 5 = 10", None)
    assert _finite_eq(solve_relation(rel, Symbol("in_var")), {5})


def test_gap9a_correctly_flipped_inequality_passes():
    rel1 = build_relation_expr(r"-2x > 6", "x")
    rel2 = build_relation_expr(r"x < -3", "x")
    assert sets_consistent(solve_relation(rel1, x), solve_relation(rel2, x)) is True


def test_gap9b_forgetting_to_flip_is_flagged():
    rel1 = build_relation_expr(r"-2x > 6", "x")
    rel2 = build_relation_expr(r"x > -3", "x")  # the classic forgot-to-flip error
    assert sets_consistent(solve_relation(rel1, x), solve_relation(rel2, x)) is False


def test_gap10_sqrt_and_pi():
    rel = build_relation_expr(r"x = \sqrt{16}", "x")
    assert _finite_eq(solve_relation(rel, x), {4})


def test_gap11_coordinate_pair_not_mistaken_for_decimal_comma():
    assert normalize_latex(r"(2,3)") == "(2,3)"


def test_gap12_unicode_minus_sign():
    rel = build_relation_expr("x = 5 − 3", "x")
    assert _finite_eq(solve_relation(rel, x), {2})


def test_gap13_checkmark_glyph_in_check_step_does_not_break_parsing():
    # Found via the step 6 live /tutor/message smoke test: a real Claude
    # reply wrote its substitution check as "$$15 = 15 ✓$$". sympy
    # auto-simplifies Eq(15, 15) to the singleton `True` rather than
    # keeping it as an Eq with .lhs/.rhs -- both sides are already equal
    # literals, so there's nothing left to represent symbolically.
    rel = build_relation_expr("15 = 15 ✓", None)
    assert rel.free_symbols == set()
    assert rel is sympy.true


def test_gap13_checkmark_does_not_collide_with_solving_variable():
    # Before the fix, "✓" parsed as a bare one-letter symbol and
    # collided with the real solving variable (e.g. x), making
    # free_symbols_of() see TWO free symbols on a step that should have
    # zero -- see test_math_guard.py's full-response version of this.
    free_syms, parts = free_symbols_of("15 = 15 ✓")
    assert free_syms == set()
    assert parts is not None


def test_gap14_text_command_with_units_is_stripped():
    """Found 13 Nov 2026 via the first live Physical Sciences smoke
    test: Maths worked examples never put units inside a $$...$$ block,
    so "\text{...}" was never exercised before -- the generic
    backslash-stripping fallback turned "\text{ m/s}" into the literal,
    unparseable "text{ m/s}". Dropped entirely now, same as a markdown
    artifact or decorative symbol."""
    assert normalize_latex(r"v = 10 \text{ m/s}") == "v = 10"
    assert normalize_latex(r"d_x = 43.3 \text{ m}") == "d_x = 43.3"


def test_gap14_text_command_lets_a_unit_bearing_answer_parse_as_one_symbol():
    free_syms, parts = free_symbols_of(r"v_f = 10 \text{ m/s}")
    assert free_syms == {Symbol("v_f")}
    assert parts is not None


def test_gap15_latex_relation_operators_were_previously_dead_code():
    r"""Found 13 Nov 2026 alongside gap 14: normalize_latex's generic
    backslash-stripping fallback already turned "\leq" into the bare
    word "leq" BEFORE split_relation ever ran on the result, so the
    backslash-form patterns in _REL_OPERATORS could never match --
    every existing inequality regression test used plain ASCII (-2x >
    6), never LaTeX's own \leq/\geq/\neq, so this was never caught.
    Real Claude output written in proper LaTeX would have silently
    failed to parse any inequality at all."""
    rel = build_relation_expr(r"x \leq 5", "x")
    assert rel == (x <= 5)
    rel = build_relation_expr(r"x \geq 5", "x")
    assert rel == (x >= 5)
    rel = build_relation_expr(r"x \neq 5", "x")
    assert rel == sympy.Ne(x, 5)


def test_gap15_approx_is_treated_as_equality_for_verification():
    # A clean two-term "\approx" block (e.g. a final numeric answer
    # rounded for display) is treated as equality. A block with a
    # DIFFERENT relation already in it earlier (e.g. "d = ... \approx
    # 50", a three-term chain) is a known, separate, pre-existing
    # limitation of the single-split parser -- not something this gap
    # claims to fix, and not tested here as a false guarantee.
    free_syms, parts = free_symbols_of(r"x \approx 5")
    assert parts == ("x", "=", "5")
    assert free_syms == {x}


def test_gap16_trig_of_literal_degree_value_no_parens():
    r"""Found 13 Nov 2026: a Physical Sciences worked example evaluated
    cos/sin AT a known numeric angle written WITH a literal degree sign
    and no parentheses at all ("\cos30°") -- different from gap 4's
    bare-SYMBOL case (sin(theta), degrees assumed by convention, no
    literal degree sign). Without parentheses, "cos30" is a single
    token to sympy's tokenizer, not a function call -- resolved
    deterministically via regex before sympy ever sees it."""
    rel = build_relation_expr(r"d_x = 50 \times \cos30°", None)
    assert abs(float(rel.rhs) - 43.301270189) < 1e-6


def test_gap16_trig_of_literal_degree_value_with_parens():
    rel = build_relation_expr(r"d_y = 50 \times \sin(30°)", None)
    assert abs(float(rel.rhs) - 25.0) < 1e-6


def test_gap16_bare_leftover_degree_sign_is_stripped():
    # After a genuine trig-argument degree sign is consumed by gap 16's
    # conversion, any OTHER bare degree sign (a final angle answer, not
    # a trig argument) is just decorative and should be dropped, same
    # convention as gap 4's bare-angle-number-means-degrees assumption.
    assert normalize_latex("theta = 30°") == "theta = 30"


def test_gap17_chain_tolerance_accepts_caps_style_rounding():
    """Found 13 Nov 2026: CAPS Physical Sciences convention rounds an
    intermediate trig value to 3 sig figs and carries the ROUNDED value
    forward (e.g. cos(30 deg) ~ 0.866, then 50*0.866 = 43.3) -- a normal,
    expected difference from the full-precision 50*cos(30deg)=43.30127,
    not a mathematical error. The flat gap-5 NUMERIC_TOLERANCE (1e-6) is
    right for Maths's exact arithmetic but was flagging this as
    inconsistent; CHAIN_RELATIVE_TOLERANCE widens chain comparison only,
    not gap 5's own guarantee (see the next test)."""
    earlier = finite_real_floats(sympy.FiniteSet(43.3012701892219))  # 50*cos(30 deg), full precision
    later = finite_real_floats(sympy.FiniteSet(43.3))  # 50*0.866, CAPS-rounded
    assert is_numeric_subset(later, earlier) is True


def test_gap17_does_not_weaken_gap5c_genuinely_wrong_step():
    # Regression guard: gap 17's wider relative tolerance must not mask
    # a real error -- x=2 vs x=7 is nowhere near a rounding difference.
    rel1 = build_relation_expr(r"x = 2", "x")
    rel2 = build_relation_expr(r"x = 7", "x")
    assert sets_consistent(solve_relation(rel1, x), solve_relation(rel2, x)) is False


def test_gap18_cube_root_surd_parses_and_solves():
    r"""Found 13 Nov 2026 while scoping Grade 11's Exponents and Surds
    topic: \sqrt[n]{X} (an indexed root) was never handled --
    convert_sqrt only matches \sqrt immediately followed by '{', so it
    silently dropped "\sqrt" and left "[3]{8}" behind as inert,
    unparseable text."""
    assert normalize_latex(r"\sqrt[3]{8}") == "((8))**(1/(3))"
    rel = build_relation_expr(r"x = \sqrt[3]{27}", "x")
    assert _finite_eq(solve_relation(rel, x), {3})


def test_gap18_square_root_still_works_unaffected():
    # Regression guard: gap 18's new nth-root handling must not break
    # gap 10's plain \sqrt{} case, which has no bracketed index at all.
    assert normalize_latex(r"\sqrt{16}") == "sqrt((16))"


def test_gap19_compound_or_inequality_is_left_unverified_not_a_crash():
    """Found 13 Nov 2026 while scoping Grade 11's quadratic inequalities:
    once gap 14 strips "\text{ or }" entirely, "x < -2 \text{ or } x >
    3" collapses to "x < -2  x > 3" -- two relations with nothing left
    connecting them. The naive first-operator split used to hand
    "-2  x > 3" to sympy as a single RHS; sympy parsed THAT as its own
    relational expression, which crashed build_relation_expr's "l < r"
    with a raw TypeError once it tried to compare a relational object
    as if it were a plain expression. split_relation now rejects a
    split where either side still contains another relational operator,
    so this returns None (an honest "could not parse"), never crashes."""
    assert split_relation(normalize_latex(r"x < -2 \text{ or } x > 3")) is None
    free_syms, parts = free_symbols_of(r"x < -2 \text{ or } x > 3")
    assert parts is None


def test_gap19_does_not_reject_a_normal_single_inequality():
    # Regression guard: gap 19's new rejection must not misfire on an
    # ordinary single relation -- only a side that ITSELF still
    # contains a relational operator gets rejected.
    assert split_relation(normalize_latex(r"-2x > 6")) == ("-2x", ">", "6")


def test_gap20_trig_of_bare_symbol_no_parens_no_space():
    r"""Found 13 Nov 2026 while scoping Grade 11 Physical Sciences: a
    real, previously-seen pattern from this tutor's own live output
    (the Vectors worked example wrote "d\cos\theta" this way) -- trig
    applied directly to a bare angle SYMBOL with no space and no
    parens. Left unhandled, the generic backslash-stripping fallback
    concatenated "\cos" and "\theta" into one nonsense token
    "costheta", which sympy's implicit-multiplication parser then
    shattered into one bogus single-letter symbol per character."""
    assert normalize_latex(r"\cos\theta") == "cos(theta)"
    rel = build_relation_expr(r"d_x = 50\cos\theta", None)
    assert rel == sympy.Eq(Symbol("d_x"), 50 * sympy.cos(theta))


def test_gap20_does_not_mishandle_cos_left_right_sizing():
    # Regression guard: "\cos\left(\theta\right)" must NOT have "left"
    # mistaken for the angle name -- it's real LaTeX sizing syntax
    # around an already-explicit paren, left for the normal path.
    assert normalize_latex(r"\cos\left(\theta\right)") == "cos(theta)"


def test_gap21_letter_glued_directly_against_a_trig_call_still_multiplies():
    r"""Found 13 Nov 2026 alongside gap 20: once "\cos\theta" becomes
    "cos(theta)", a letter glued directly against it with no space or
    operator (e.g. the "d" in "d\cos\theta", or "BA" in a flux formula)
    is worse than a naming collision -- sympy's implicit-multiplication
    parser DROPS the trig call entirely and shatters the whole run into
    single-letter symbols multiplied together ("dcos(theta)" parsed as
    "c*d*o*s*theta", with no cos() anywhere in the result)."""
    free_syms, parts = free_symbols_of(r"d_x = d\cos\theta")
    assert free_syms == {Symbol("d_x"), Symbol("d"), theta}
    assert normalize_latex(r"\Phi = BA\cos\theta") == "Phi = BA*cos(theta)"


def test_gap21_does_not_double_insert_or_break_a_leading_digit():
    # Regression guard: a digit directly before a trig call already
    # parses correctly via sympy's own implicit multiplication and must
    # not be touched; an already-explicit "*" must not be duplicated.
    assert normalize_latex(r"2\cos\theta") == "2cos(theta)"
    assert normalize_latex(r"d*\cos\theta") == "d*cos(theta)"


def test_gap22_braced_text_subscript_normalizes_to_valid_identifier():
    r"""Found 13 Nov 2026 via the live Electric Circuits stress test (a
    real series-parallel resistor problem): a multi-character LaTeX
    subscript wrapped in braces, with a nested \text{...} naming it
    (e.g. "R_{\text{parallel}}"), was never converted into a valid
    sympy identifier at all. Worse, it collided with gap 14's
    strip_text_commands -- which runs first and unconditionally drops a
    \text{...} group wherever it appears -- so "R_{\text{parallel}}"
    lost its \text{parallel} entirely but kept the subscript's own
    now-empty braces behind, producing the literal "R_{}", which
    sympy's parser cannot accept as syntax at all (a bare "{" is not
    valid). convert_braced_subscript must run BEFORE strip_text_commands
    to avoid this."""
    assert normalize_latex(r"R_{\text{parallel}}") == "R_parallel"
    assert normalize_latex(r"I_{\text{each}} = \frac{I_{\text{total}}}{2}") == (
        "I_each = ((I_total))/((2))"
    )


def test_gap22_braced_digit_and_unit_symbol_subscript_normalizes_too():
    r"""Same gap, the other common shape: a subscript combining a
    literal digit with a unit-symbol LaTeX command, e.g. "V_{3\Omega}"
    (the resistor's own ohm value folded into its variable name). No
    \text{...} is involved here, but the braces themselves were still
    never stripped before this fix -- "V_{3\Omega}" normalized to the
    syntactically invalid "V_{3Omega}" (braces intact), not a bare
    identifier."""
    assert normalize_latex(r"V_{3\Omega}") == "V_3Omega"
    free_syms, parts = free_symbols_of(r"P_{3\Omega} = I^2 \times R_{3\Omega}")
    assert free_syms == {Symbol("P_3Omega"), Symbol("I"), Symbol("R_3Omega")}
    assert parts == ("P_3Omega", "=", "I**2 * R_3Omega")


def test_gap22_does_not_touch_an_already_simple_digit_subscript():
    # Regression guard: a single-digit subscript with NO braces (R_1,
    # R_2) was already a legal identifier as-is and must be left alone.
    assert normalize_latex(r"R_1 + R_2") == "R_1 + R_2"


def test_gap23_boxed_final_answer_is_unwrapped():
    r"""Found 15 Nov 2026 via the first live Grade 12 Differential
    Calculus test (exactly the risk ADR-022 flagged as untested when
    Grade 12 content was added): a final boxed answer --
    \boxed{f'(x) = 2x + 3} -- reached sympy's parser as a literal,
    unparseable fragment. \boxed{...} is purely presentational, so it
    is unwrapped, keeping everything inside intact."""
    assert normalize_latex(r"\boxed{2x + 3}") == "2x + 3"


def test_gap23_prime_notation_parses_without_crashing():
    r"""f'(x)/g'(x)-style derivative notation: a bare apostrophe is not
    valid syntax anywhere sympy's parser accepts, so this previously
    failed to parse at all (a crash risk, same class as gap 19). Renamed
    consistently to a plain, distinct name so it parses -- deliberately
    NOT claimed to be related back to f symbolically, so it still (and
    correctly) falls into the existing multi-symbol 'left unverified'
    territory, not a false single-variable solve."""
    free_syms, parts = free_symbols_of(r"f'(x) = 2x + 3")
    assert parts is not None  # must actually parse, not raise/return None
    assert len(free_syms) > 1  # honest: the function-name token is its own symbol too


def test_gap23_limit_of_a_simple_expression_evaluates():
    r"""The single most common first-principles shape -- \lim_{h \to 0}
    applied to a plain polynomial in x and h with no undefined function
    calls inside it -- is now actually evaluated via sympy's real
    limit(), eliminating h entirely, rather than left as unparseable
    text."""
    assert normalize_latex(r"\lim_{h \to 0}(2x + h + 3)") == "limit(((2x + h + 3)), h, 0)"
    free_syms, parts = free_symbols_of(r"\lim_{h \to 0}(2x + h + 3) = 2x + 3")
    assert free_syms == {Symbol("x")}


def test_gap23_standalone_limit_evaluation_is_now_a_real_numeric_check():
    """A direct 'evaluate this limit' problem (no first-principles
    function-label noise at all) now becomes a genuine, fully checkable
    zero-free-symbol step once the limit variable is eliminated -- this
    is the concrete new verification coverage this gap buys, not just
    quieter warning text."""
    free_syms, parts = free_symbols_of(r"\lim_{x \to 2}(x^2 + 3x) = 10")
    assert free_syms == set()
    assert parts == ("limit(((x**2 + 3x)), x, 2)", "=", "10")


def test_gap23_limit_subscript_marker_does_not_collide_with_gap22():
    r"""Regression guard for a real interaction found while building this
    fix: convert_braced_subscript's own "letters immediately followed by
    _{" pattern used to misread "\lim_{h \to 0}" as if "lim" were a
    plain subscripted variable (mangling it into the unparseable
    "lim_hto0(...)" before the limit converter ever saw the real text).
    Fixed with a negative lookbehind for a preceding backslash OR letter
    on _BASE_BRACED_SUBSCRIPT -- confirms gap 22's own real subscript
    case (no backslash immediately before the base letter) still works
    exactly as before."""
    assert normalize_latex(r"R_{\text{total}}") == "R_total"
    assert normalize_latex(r"\lim_{h \to 0}(2x + h + 3)") == "limit(((2x + h + 3)), h, 0)"
