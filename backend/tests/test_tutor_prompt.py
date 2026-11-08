"""
Unit tests for app.services.tutor.build_tutor_system_prompt(). Pure --
no DB, no network.
"""

from app.services.tutor import build_tutor_system_prompt


def test_contains_worked_example_anchor():
    prompt = build_tutor_system_prompt("Quadratic Equations", "personalization block")
    assert "2x + 5 = 15" in prompt


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
