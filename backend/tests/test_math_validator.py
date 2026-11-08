"""
One regression test per numbered gap in REBUILD_SPEC.md Section 1's
MathGuard section (and ADR-011) -- each of these reproduces a specific,
previously real, documented bug. Pure -- no DB, no network, no sympy
Internet access needed.
"""

from sympy import Symbol

from app.services.math_validator import (
    build_relation_expr,
    finite_real_floats,
    normalize_latex,
    sets_consistent,
    solve_relation,
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
