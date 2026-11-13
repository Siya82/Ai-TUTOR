"""
Integration tests for app.services.math_guard.verify_tutor_response() --
full tutor-response text in, (verified, warnings) out. Pure -- no DB,
no network.
"""

from app.services.math_guard import verify_tutor_response


def test_consistent_chain_with_a_trailing_check_step_passes():
    # Exactly the gap-3 scenario: a "check your answer" step must not be
    # chain-compared against the solving sequence.
    text = """
Step 1: Subtract 5 from both sides.
$$2x + 5 = 15$$
$$2x = 10$$
Step 2: Divide by 2.
$$x = 5$$
Let's check our answer:
$$2(5) + 5 = 15$$
"""
    result = verify_tutor_response(text)
    assert result.verified is True
    assert not any("does not" in w for w in result.warnings)


def test_a_wrong_check_step_is_flagged():
    text = "$$2x + 5 = 15$$\n$$x = 5$$\n$$2(5) + 5 = 16$$"
    result = verify_tutor_response(text)
    assert result.verified is False
    assert any("does not hold numerically" in w for w in result.warnings)


def test_a_wrong_solving_step_is_flagged():
    text = "$$2x + 5 = 15$$\n$$x = 100$$"
    result = verify_tutor_response(text)
    assert result.verified is False
    assert any("does not follow from the previous one" in w for w in result.warnings)


def test_geometry_proof_is_an_honest_limitation_not_a_false_verdict():
    text = (
        "The diagonals of a parallelogram bisect each other, because triangles "
        "ABE and CDE are congruent (AAS)."
    )
    result = verify_tutor_response(text)
    assert result.verified is True  # no contradiction found -- not a false "passed" claim either
    assert len(result.warnings) == 1
    assert "geometry proof" in result.warnings[0]


def test_multi_symbol_identity_is_left_unverified_not_flagged_false():
    text = "$$a^{2} + 2ab + b^{2} = (a+b)^{2}$$"
    result = verify_tutor_response(text)
    assert result.verified is True
    assert any("Left unverified" in w for w in result.warnings)


def test_prose_header_text_does_not_bleed_into_a_capture():
    text = "## Step 1: Solving for x\n$$2x = 10$$\n$$x = 5$$"
    result = verify_tutor_response(text)
    assert result.verified is True


def test_no_math_blocks_at_all_is_also_an_honest_limitation():
    result = verify_tutor_response("Great question! Let me explain conceptually without equations.")
    assert result.verified is True
    assert len(result.warnings) == 1


def test_gap13_checkmark_in_real_live_captured_response_is_fully_verified():
    # The exact reply text captured from the step 6 live /tutor/message
    # smoke test, before the gap-13 fix: this used to come back with
    # "Multiple different variables appear across solving steps (['x', '✓'])"
    # even though every step was mathematically correct -- the checkmark
    # glyph in the final "$$15 = 15 ✓$$" check step was being parsed as a
    # second symbol. Now fully verified with zero warnings.
    text = (
        "## Solving: $$2x + 5 = 15$$\n"
        "Step 1: Subtract 5 from both sides:\n$$2x + 5 - 5 = 15 - 5$$\n$$2x = 10$$\n"
        "Step 2: Divide both sides by 2:\n$$\\frac{2x}{2} = \\frac{10}{2}$$\n$$x = 5$$\n"
        "Check: substitute x = 5 back into the original equation:\n"
        "$$2(5) + 5 = 15$$\n$$10 + 5 = 15$$\n$$15 = 15 ✓$$\n"
    )
    result = verify_tutor_response(text)
    assert result.verified is True
    assert result.warnings == []


def test_physical_sciences_live_captured_response_now_fully_verified():
    # The exact reply text captured from the first live /tutor/message
    # smoke test against Physical Sciences (13 Nov 2026), before gaps
    # 14-17 were fixed: this used to come back verified=False, flagged
    # by two false "does not follow from the previous one" errors on
    # pedagogically-correct, properly-rounded steps (gap 17), after
    # most of its lines failed to parse at all because of inline units
    # (gap 14) -- see BUILD_LOG.md's 13 Nov 2026 entry for the full
    # investigation. Now verified=True; the handful of remaining
    # warnings are genuinely unverifiable content (prose restating a
    # given value, general vector/kinematics identities, and one
    # three-term "d = ... \approx ... check" chain the single-split
    # parser was never designed to handle) -- an honest limitation, not
    # a bug.
    text = (
        "$$\\vec{d} = 50 \\text{ m at } 30°\\text{ above horizontal}$$\n"
        "$$d_x = d\\cos\\theta$$\n"
        "$$d_x = 50 \\times \\cos30°$$\n"
        "$$d_x = 50 \\times 0.866$$\n"
        "$$d_x = 43.3 \\text{ m}$$\n"
        "$$d_y = d\\sin\\theta$$\n"
        "$$d_y = 50 \\times \\sin30°$$\n"
        "$$d_y = 50 \\times 0.5$$\n"
        "$$d_y = 25 \\text{ m}$$\n"
        "$$d = \\sqrt{d_x^2 + d_y^2}$$\n"
        "$$d = \\sqrt{(43.3)^2 + (25)^2}$$\n"
        "$$d = \\sqrt{1874.9 + 625}$$\n"
        "$$d = \\sqrt{2499.9} \\approx 50 \\text{ m} ✓$$\n"
        "$$v_f = v_i + at$$\n"
        "$$v_f = 0 + (2)(5)$$\n"
        "$$v_f = 10 \\text{ m/s}$$\n"
    )
    result = verify_tutor_response(text)
    assert result.verified is True
    assert not any("does not follow" in w or "does not hold" in w for w in result.warnings)


def test_solving_for_two_different_quantities_in_one_response_both_get_checked():
    """Regression test for the 13 Nov 2026 per-symbol-grouping fix: a
    response that correctly solves for TWO different quantities (not
    just leaves extra content unverified, but actually gets each one
    right) must verify both chains, not throw both away just because
    more than one symbol appears across the whole response."""
    text = "$$d_x = 10$$\n$$d_x = 10$$\n$$v_f = 5$$\n$$v_f = 5$$"
    result = verify_tutor_response(text)
    assert result.verified is True
    assert not any("Multiple different variables" in w for w in result.warnings)


def test_solving_for_two_different_quantities_a_wrong_one_is_still_caught():
    # Same shape as above, but the d_x chain is wrong -- must still be
    # flagged, even though v_f's chain (a different symbol) is fine.
    text = "$$d_x = 10$$\n$$d_x = 99$$\n$$v_f = 5$$\n$$v_f = 5$$"
    result = verify_tutor_response(text)
    assert result.verified is False
    assert any("does not follow from the previous one" in w for w in result.warnings)


def test_gap19_compound_inequality_answer_does_not_crash_verification():
    """Found 13 Nov 2026 while scoping Grade 11's quadratic inequalities
    (Equations and Inequalities topic): a factorised quadratic
    inequality's natural answer is a compound/union statement, e.g.
    "x < -2 or x > 3". Once rendered in LaTeX ("x < -2 \\text{ or } x >
    3") and run through gap 14's \\text{...} stripping, this used to
    raise a raw, uncaught TypeError out of verify_tutor_response --
    a real crash risk for the live /tutor/message endpoint, not just a
    lost warning. Must now degrade to an honest "could not verify",
    with the rest of the response (the correct, equation-shaped steps
    before it) still verified normally."""
    text = (
        "$$x^2 - x - 6 > 0$$\n"
        "$$(x - 3)(x + 2) > 0$$\n"
        "$$x < -2 \\text{ or } x > 3$$"
    )
    result = verify_tutor_response(text)  # must not raise
    assert result.verified is True
    assert any("Could not parse" in w for w in result.warnings)


def test_gap18_cube_root_surd_in_a_real_reply_verifies_cleanly():
    """Found 13 Nov 2026 while scoping Grade 11's Exponents and Surds
    topic: a worked example solving via a cube root used to produce
    unparseable garbage ("[3]{8}") for every $$...$$ block that
    contained one, leaving the whole reply unverifiable."""
    text = "$$x^3 = 27$$\n$$x = \\sqrt[3]{27}$$\n$$x = 3$$"
    result = verify_tutor_response(text)
    assert result.verified is True
    assert not any("Could not parse" in w or "does not follow" in w for w in result.warnings)
