"""
Unit test for app.services.tutor.TutorClient. Mocks the Anthropic SDK
call -- does NOT hit the real API (that's a separate, explicitly
@pytest.mark.live_api-marked test to add later, per REBUILD_SPEC.md
Section 6 / ADR-010).
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services.tutor import MAX_TOKENS, TutorClient


@pytest.mark.asyncio
async def test_ask_passes_system_param_and_extracts_response_text():
    client = TutorClient(api_key="sk-ant-test-not-real", model="claude-sonnet-4-6")

    fake_response = SimpleNamespace(content=[SimpleNamespace(text="4 and a half times 3 is 13.5")])
    client._client.messages.create = AsyncMock(return_value=fake_response)

    result = await client.ask("SYSTEM PROMPT HERE", [{"role": "user", "content": "hi"}])

    assert result == "4 and a half times 3 is 13.5"
    client._client.messages.create.assert_awaited_once_with(
        model="claude-sonnet-4-6",
        max_tokens=MAX_TOKENS,
        system="SYSTEM PROMPT HERE",
        messages=[{"role": "user", "content": "hi"}],
    )
