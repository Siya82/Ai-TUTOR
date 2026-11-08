"""
Unit tests for app.services.tutor.build_tutor_system_prompt(). Pure --
no DB, no network.
"""

from app.services.tutor import build_tutor_system_prompt


def test_contains_worked_example_anchor():
    prompt = build_tutor_system_prompt("Quadratic Equations", "personalization block")
    assert "2x + 5 = 15" in prompt


def test_worked_example_anchor_uses_dollar_delimiters():
    """Regression test for the 8 Nov 2026 fix found via the step 6 live
    smoke test: the calibration anchor itself must demonstrate the
    $$...$$ format, not just plain "Step 1: ... = ..." text -- Claude
    follows the example's formatting, not just the rule describing it."""
    prompt = build_tutor_system_prompt("Quadratic Equations", "personalization block")
    assert "$$2x + 5 = 15$$" in prompt
    assert "$$x = 5$$" in prompt


def test_contains_math_formatting_rule():
    """Regression test: without an explicit instruction to wrap equations
    in $$...$$, MathGuard (which only extracts $$...$$ blocks) never has
    anything to verify in a real Claude response -- math_verified would
    always be True with a "no blocks found" warning, silently never
    doing its job. Caught via the step 6 live /tutor/message smoke test,
    not a unit test -- see BUILD_LOG.md."""
    prompt = build_tutor_system_prompt("Quadratic Equations", "personalization block")
    assert "MATH FORMATTING RULE" in prompt
    assert "$$" in prompt


def test_contains_explain_why_rule():
    prompt = build_tutor_system_prompt("Quadratic Equations", "personalization block")
    assert "NON-NEGOTIABLE" in prompt
    assert "WHY" in prompt


def test_contains_rag_placeholder():
    prompt = build_tutor_system_prompt("Quadratic Equations", "personalization block")
    assert "content_chunks" in prompt


def test_contains_personalization_block_verbatim():
    prompt = build_tutor_system_prompt("Quadratic Equations", "UNIQUE_PERSONALIZATION_MARKER")
    assert "UNIQUE_PERSONALIZATION_MARKER" in prompt


def test_diagnosis_note_included_only_when_given():
    without_note = build_tutor_system_prompt("Quadratic Equations", "p-block")
    assert "DIAGNOSIS NOTE" not in without_note

    with_note = build_tutor_system_prompt("Quadratic Equations", "p-block", diagnosis_note="DIAGNOSIS NOTE: redirect")
    assert "DIAGNOSIS NOTE" in with_note


def test_topic_name_appears_in_prompt():
    prompt = build_tutor_system_prompt("Analytical Geometry", "p-block")
    assert "Analytical Geometry" in prompt
