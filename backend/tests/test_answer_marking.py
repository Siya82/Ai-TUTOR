"""
Unit tests for app.services.answer_marking.mark_answer(). Mocks
TutorClient.ask() directly (same posture as test_tutor_client.py mocks
the Anthropic SDK one layer down) -- does NOT hit the real API.
See docs/ADR-028-assignments.md.
"""

from unittest.mock import AsyncMock

import pytest

from app.services.answer_marking import mark_answer
from app.services.tutor import TutorClient


def _client_returning(raw: str) -> TutorClient:
    client = TutorClient(api_key="sk-ant-test-not-real", model="claude-sonnet-4-6")
    client.ask = AsyncMock(return_value=raw)
    return client


@pytest.mark.asyncio
async def test_marks_correct_answer_from_clean_json():
    client = _client_returning('{"is_correct": true, "feedback": "Nicely done."}')

    result = await mark_answer(
        client,
        question_text="Solve 2x + 5 = 15",
        model_answer="x = 5",
        learner_response="x = 5",
    )

    assert result.is_correct is True
    assert result.feedback == "Nicely done."


@pytest.mark.asyncio
async def test_marks_incorrect_answer():
    client = _client_returning('{"is_correct": false, "feedback": "Check your arithmetic."}')

    result = await mark_answer(
        client, question_text="2 + 2", model_answer="4", learner_response="5"
    )

    assert result.is_correct is False
    assert result.feedback == "Check your arithmetic."


@pytest.mark.asyncio
async def test_strips_markdown_json_fence():
    """Claude sometimes wraps its JSON in a ```json ... ``` fence despite
    being told not to -- this must not be treated as malformed output."""
    client = _client_returning('```json\n{"is_correct": true, "feedback": "Good."}\n```')

    result = await mark_answer(
        client, question_text="q", model_answer="a", learner_response="a"
    )

    assert result.is_correct is True
    assert result.feedback == "Good."


@pytest.mark.asyncio
async def test_malformed_json_degrades_to_unmarked_not_a_guess():
    """Regression test for ADR-028's explicit decision: malformed output
    must become is_correct=None ("unmarked"), never a guessed True or
    False that could silently corrupt the Attempt row."""
    client = _client_returning("Sure, I think that's correct!")

    result = await mark_answer(
        client, question_text="q", model_answer="a", learner_response="a"
    )

    assert result.is_correct is None
    assert result.feedback is not None  # still explains what happened, just isn't a guess


@pytest.mark.asyncio
async def test_non_boolean_is_correct_degrades_to_unmarked():
    """Malformed in a different way -- valid JSON, but is_correct isn't
    actually a JSON boolean. Must still degrade to None, not truthy-cast
    the string/number into a wrong guess."""
    client = _client_returning('{"is_correct": "yes", "feedback": "..."}')

    result = await mark_answer(
        client, question_text="q", model_answer="a", learner_response="a"
    )

    assert result.is_correct is None


@pytest.mark.asyncio
async def test_api_failure_degrades_to_unmarked():
    client = TutorClient(api_key="sk-ant-test-not-real", model="claude-sonnet-4-6")
    client.ask = AsyncMock(side_effect=RuntimeError("API is down"))

    result = await mark_answer(
        client, question_text="q", model_answer="a", learner_response="a"
    )

    assert result.is_correct is None
    assert "API is down" in result.feedback
