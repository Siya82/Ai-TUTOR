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
