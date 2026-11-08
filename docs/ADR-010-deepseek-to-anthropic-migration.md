# ADR-010: DeepSeek to Anthropic migration, and project structure cleanup

## Date
2026-08-25

## Status
Accepted

## Context
TutorClient (app/services/tutor.py) and Settings (app/core/config.py) were
wired to DeepSeek's OpenAI-compatible API rather than the Anthropic Claude
API documented as the project's actual stack. This surfaced during live-API
testing of POST /tutor/message, which failed with a 503 and the message
"DEEPSEEK_API_KEY is not configured" -- a key that was never set, since the
intended provider was always Anthropic.

Separately, a duplicate full copy of the project (ai-caps-tutor/) existed
alongside the real working tree, caused by a WinRAR/tar.gz two-step
extraction (see earlier Build Log entry). All files inside it carried an
identical, untouched timestamp (2026-08-03 16:23), confirming it was never
edited after extraction and was safe to remove from active use.

## Decision
1. Migrated TutorClient from the openai SDK (pointed at DeepSeek's
   OpenAI-compatible endpoint) to the anthropic SDK directly.
   - System prompt now passed via the dedicated 'system' parameter,
     not a {"role": "system"} message (Anthropic's message format
     does not accept a system role in the messages list).
   - Response text now read from response.content[0].text instead of
     response.choices[0].message.content.
   - Settings renamed: deepseek_api_key/deepseek_base_url/deepseek_model
     -> anthropic_api_key/anthropic_model.
2. Increased max_tokens from 1024 to 2048 in TutorClient.ask() to reduce
   the risk of truncated multi-step explanations on longer problems.
3. Fixed a datetime.utcnow() deprecation warning in
   app/services/personalization.py (now datetime.now(UTC)).
4. Archived ai-caps-tutor/ as _ARCHIVE_ai-caps-tutor-DO-NOT-USE/ at the
   project root. Ai_TUTOR/ (not ai-caps-tutor/) is the canonical project
   root going forward; all scripts, docker-compose, and pytest run from
   there.

## Verification
Added tests/test_tutor_live_api.py, marked @pytest.mark.live_api and
excluded from default pytest runs (see pytest.ini addopts). Confirmed
against real seeded data (Algebra topic, Test Student learner):
- POST /tutor/message returns 200 with a genuine Claude-generated
  explanation that correctly names the subtraction and division steps
  for the 2x+5=15 calculation anchor.
- Invalid input still returns 400/422 without leaking the API key.

## Consequences
- .env and .env.example were already correctly using ANTHROPIC_API_KEY /
  ANTHROPIC_MODEL, so no environment changes were needed -- only code and
  config field names.
- Anyone running scripts/seed_dev_data.py again will hit a
  UniqueViolationError on the Mathematics subject, since seed data
  already exists from an earlier run. This is expected, not a bug.
