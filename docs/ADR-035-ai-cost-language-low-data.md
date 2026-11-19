# ADR-035: AI cost controls, home-language help, installable low-data app

**Date:** 19 Nov 2026 · **Status:** Accepted (Siya: "do as per your recommendation")

## Context
The SamarthX comparison showed THUTOra's reach depends on cost per learner,
learners on prepaid data, and learners who think in a language other than
English.

## Decision
- **Cost:** the tutor's system prompt is sent as a cacheable block (Anthropic
  prompt caching). Answer marking may use a cheaper model via `MARKING_MODEL`
  in `.env` (empty = `ANTHROPIC_MODEL`); marking is capped at 600 output tokens.
  Chat history was already capped at 20 turns (code review #4).
- **Home language:** learners choose "Also explain in" (the 11 official
  languages; `learners.home_language`, migration 0014). The tutor still teaches
  in English, the exam language, but may explain in the home language and must
  keep English subject terms and never translate formulas.
- **Installable, low-data:** a web manifest + icons and a service worker
  (`public/sw.js`) that caches only the app shell, never API responses
  (personal data). Production builds only. "Save data" (per device) makes
  textbook figures load on tap; equations always load. Book assets already
  carry a 7-day private cache header.

## Not done
- Zero-rating is an application to the mobile networks (THUTOra must offer
  learners free, unconditional access to qualify).
- Prompt caching uses `cache_control` blocks; the pinned SDK (0.39) passes
  them through. Confirm the cache hit rate in the Anthropic console once live.
