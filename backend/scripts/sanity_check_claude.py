"""
Standalone live-API sanity check for the Anthropic key in .env --
isolates just the Claude call from the rest of the stack (no DB, no
FastAPI, no other services) so a credential problem can be diagnosed
in seconds instead of by restarting uvicorn and sending a full
/tutor/message request each time.

REBUILD NOTE: listed in REBUILD_SPEC.md Section 4 as known to have
existed under this exact name, but never recovered -- purpose inferred
from the name alone. This is a genuine (re)write, not a recovery.

Never prints the key itself -- only whether Settings loaded one, its
length, and the API's own response.

Run from backend/, with the venv active:
    python -m scripts.sanity_check_claude
"""

import asyncio

from anthropic import AsyncAnthropic

from app.core.config import settings


async def main() -> None:
    key = settings.anthropic_api_key
    model = settings.anthropic_model

    if not key:
        print("FAIL: ANTHROPIC_API_KEY is empty/unset in .env -- nothing to test.")
        return

    print(f"Settings loaded an API key ({len(key)} characters) and model '{model}'.")
    print("Sending a minimal live request to the Anthropic API...")

    client = AsyncAnthropic(api_key=key)
    try:
        response = await client.messages.create(
            model=model,
            max_tokens=16,
            messages=[{"role": "user", "content": "Reply with exactly one word: OK"}],
        )
    except Exception as exc:
        print(f"FAIL: {type(exc).__name__}: {exc}")
        print()
        print("If this is an AuthenticationError (401, 'invalid x-api-key'):")
        print("  - Open backend\\.env yourself and check ANTHROPIC_API_KEY=... --")
        print("    look for a stray leading/trailing space, a quote character")
        print("    copied in by mistake, or a character missing from the paste.")
        print("  - Confirm the key is still active at console.anthropic.com --")
        print("    it may have been revoked/rotated, or be a key from the wrong")
        print("    organization/workspace.")
        print("  - Do not paste the key itself into chat -- edit .env directly.")
        return

    print(f"SUCCESS: model replied: {response.content[0].text!r}")


if __name__ == "__main__":
    asyncio.run(main())
