# ADR-005: Video Resources, Interactive Content, and Virtual Labs

**Status:** Accepted
**Date:** 2026-07-31

## Context

The product owner wants video resources, interactive content, and virtual
labs where learners manipulate variables (e.g. reacting substances,
taking measurements) and see realistic results, on mobile devices.

## Decision

### Video — curate, don't produce
Free, CAPS-aligned video content already exists at scale: Mindset Learn,
Siyavula, and Khan Academy all provide curriculum-aligned video content
for Grade 10–12 Maths and Physical Sciences. Building a video production
or AI-video-generation pipeline would duplicate existing, validated
content at high effort for no real gain. `VideoResource` is a thin
metadata table linking learners from a `Topic` to an external, curated
video — not a hosting or generation system.

### Interactive labs — two tiers, deliberately not one open sandbox

**Tier 1 — embed existing validated simulations.** PhET Interactive
Simulations (University of Colorado) are free, open, and already used by
South African Physical Sciences teachers. Where a PhET simulation exists
for a CAPS topic, embed/link it rather than rebuild it. PhET's chemistry
and physics engines are scientifically validated by domain experts —
something a small team cannot credibly replicate to the same standard in
a pilot timeframe.

**Tier 2 — build only for CAPS-prescribed practicals PhET doesn't cover.**
Grade 10 Physical Sciences has a small, fixed, official list of prescribed
practical experiments (not an open "mix any element" sandbox). Where we
build, we build exactly those experiments, with:
- Fixed, learner-adjustable input parameters that match the real practical
  (e.g. mass of magnesium, concentration and volume of acid) — not
  arbitrary substance combinations.
- **Results computed by deterministic formulas in code, never by the
  LLM.** The AI's role is to explain/narrate a result that code already
  calculated correctly — the same "grounded, not improvised" principle as
  the tutor (ADR-003) and the curriculum content (ADR-001). Letting an
  LLM freehand a chemistry outcome risks confidently stating something
  false in a subject where that's actively harmful to learn.
- Physical constants (molar volumes, molar masses, etc.) explicitly
  flagged in code for verification against the official CAPS/DBE Data
  Booklet before any pilot use — never presented as authoritative without
  that check.

### Explicitly rejected: open-ended "mix any element at any measurement"
This was the original framing in the request. Rejected because accurate,
general-purpose chemical reaction simulation (arbitrary reactants,
arbitrary quantities, correct products, correct hazards) is a genuinely
hard scientific engineering problem — it is most of what PhET's domain
experts spent years building. A smaller, less validated version of that
would either be very limited in disguise (silently only "working" for a
few hardcoded combinations) or would produce wrong chemistry for anything
outside that hardcoded set, which is worse than not having the feature.

## Consequences

- Faster to ship: most "interactive lab" value comes from embedding PhET,
  not building physics/chemistry engines.
- Content curation (tagging the right video/simulation to the right CAPS
  topic) becomes real, ongoing work — not a one-time build.
- Building only the prescribed-practicals list keeps scope bounded and
  makes "did we get the chemistry right" a checkable, finite task instead
  of an open-ended one.
