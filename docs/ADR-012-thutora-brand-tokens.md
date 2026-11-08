# ADR-012: THUTOra brand tokens supersede the original Zynora tokens

**Status:** Accepted
**Date:** 2026-11-08

## Context

ADR-008 defined the frontend's design tokens by sampling pixel data
directly from the original Zynora logo (black `#000000`, white
`#FFFFFF`, cyan `#00EEFD`). That ADR's own "Update (per later project
record)" note flagged that by the time of the crash, the frontend was
actually being re-skinned toward a different, newer palette taken from
the supplied THUTOra brand sheet -- but said explicitly that "whichever
palette is authoritative should be decided explicitly on rebuild rather
than left implicit." `THUTOra_Project_Report.md` repeated this as an
open decision under "Brand & scope reconciliation."

This had to be resolved before building step 7 (the frontend chat UI),
since every component's styling depends on it.

## Decision

The THUTOra brand-sheet palette is authoritative, confirmed explicitly
by Siya on rebuild (8 Nov 2026) rather than assumed:

| Token | Value |
|---|---|
| `--thutora-navy` | `#0D1B2A` |
| `--thutora-teal` | `#00BFA6` |
| `--thutora-purple` | `#6C5CE7` |
| `--thutora-green` | `#4CAF50` |
| `--thutora-orange` | `#FF9F1C` |
| `--thutora-offwhite` | `#F4F6FA` |

`frontend/src/styles/tokens.css` was rewritten with these as the raw
tokens, keeping the same semantic-alias layer ADR-008 established
(`--color-background`, `--color-accent`, etc., with teal now the
primary accent and purple as a secondary accent). `product-tokens.css`
(the file `App.jsx` actually imports, never recovered verbatim) is a
one-line `@import` of `tokens.css`, so there is one source of truth,
not two palettes to keep in sync.

Surface tiers (`--thutora-surface-1/2`), muted text, and the
"on-accent" text color are this rebuild's own reasonable dark-UI
additions -- not sampled from any brand asset, same role as the
equivalent ADR-008 additions were.

Green and orange were not given semantic roles in ADR-008's simpler
three-color scheme; this rebuild assigns them `--color-success` /
`--color-warning` respectively, since the chat UI needs both (a
MathGuard "verified" badge, a "needs support" pace-tier indicator,
risk-dashboard flags) and the brand sheet already supplies colors
suited to exactly that purpose.

## Consequences

- `demo/tokens-demo.html` (ADR-008's visual verification page) was
  updated to the new tokens and wordmark/tagline, so it still does its
  job of letting the palette be checked visually.
- Any future design asset (a Figma file, an updated brand book) should
  still take precedence over this table if it specifies different exact
  values, per ADR-008's own caveat -- this ADR records what was
  explicitly confirmed on 8 Nov 2026, not a permanent lock.
- ADR-008 is left as historical record of the original Zynora
  tokens and the reasoning that led to this supersession -- not deleted
  or rewritten.
