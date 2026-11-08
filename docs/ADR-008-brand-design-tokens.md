# ADR-008: Brand Design Tokens (Zynora Technologies)

**Status:** Accepted
**Date:** 2026-08-02

## Context

The project is owned by Zynora Technologies. A CSS color scheme needs to
be derived from the official logo for use across the frontend.

## Decision

Colors were **measured directly from logo pixel data**, not eyeballed —
sampled at the background, the "ZYNORA" wordmark, and three independent
cyan accent points (the dot above the Z, the "TECHNOLOGIES" subtitle
text, the accent dot inside the "A") to confirm all three cyan
appearances are the same brand color rather than visually-similar but
distinct ones.

| Token | Measured value | Sample source |
|---|---|---|
| `--zynora-black` | `#000000` | Background, sampled RGB(0,0,3) |
| `--zynora-white` | `#FFFFFF` | Wordmark, sampled RGB(255,255,255) exactly |
| `--zynora-cyan` | `#00EEFD` | Average of 4 samples: `#00DEF5`, `#00FEFF`, `#00EBFF`, `#00F3FF` |

The four cyan samples ranged narrowly (`#00DE`–`#00FE` on the green
channel), which is consistent with the same brand color rendered with
some glow/bloom variance rather than genuinely different colors — a
useful sanity check that this is one accent color, not several.

Surface levels (`--zynora-surface-1`, `--zynora-surface-2`) and muted
text (`--zynora-text-secondary`) are **not** sampled from the logo — the
logo doesn't contain UI surface examples. These are standard dark-UI
practice additions for creating depth/hierarchy without introducing a
new hue, clearly separated from measured tokens in the token file's
comments.

Tokens are exposed as plain CSS custom properties (`frontend/src/styles/
tokens.css`), with semantic aliases (`--color-background`, `--color-
accent`, etc.) layered on top of the raw brand tokens — components should
reference the semantic aliases, not `--zynora-*` directly, so the palette
can be adjusted later without touching every component.

## Consequences

- Framework-agnostic: works with plain CSS, CSS Modules, or as the source
  for a Tailwind theme extension if the frontend adopts Tailwind later.
- A demo file (`demo/tokens-demo.html`) exists to visually verify the
  tokens render as intended.
- If Zynora has an official brand guideline document (Figma file, brand
  book) with exact specified hex values, that should take precedence over
  these sampled values — sampling a PNG is a good-faith extraction, not a
  substitute for an authoritative source if one exists.

## Update (per later project record)

As of the THUTOra rebrand, the frontend was being scaffolded with a
different, newer palette — navy `#0D1B2A`, teal `#00BFA6`, purple
`#6C5CE7` — taken from the supplied THUTOra brand sheet rather than these
originally-sampled Zynora tokens. Whichever palette is authoritative
should be decided explicitly on rebuild rather than left implicit; see
REBUILD_SPEC.md.
