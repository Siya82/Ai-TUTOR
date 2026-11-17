# ADR-034: Light theme with one colour per product

**Date:** 17 Nov 2026
**Status:** Accepted (Siya approved the mockup; "THUTOra product colours" design canvas)

## Context
THUTOra has four products (LEARN, TEACH, CONNECT, INSIGHTS) but the app used
one dark navy theme with a single teal accent (ADR-012). Siya's mockup asked
for a recognisable colour per product, used sparingly: coloured icon
backgrounds with matching strokes, navy text, mostly white cards.

## Decision
- Light theme: page `#F6F8FB`, white surfaces, border `#E3E8EF`, navy text
  `#0D1B2A`, muted text `#5B6B7F`.
- Product colours (slightly darker than the mockup so white text on them and
  their strokes on white pass WCAG AA):
  LEARN green `#15803D`, TEACH purple `#6D28D9`, INSIGHTS blue `#1D4ED8`,
  CONNECT orange `#C2410C`, each with a soft tint.
- A product's area sets `data-product="learn|teach|insights|connect"`;
  tokens.css re-declares `--color-accent`, `--color-accent-hover` and
  `--color-accent-tint` under each, so existing components pick up the right
  colour with no per-component changes.
- Student app root is LEARN. Teacher app root is TEACH; the Progress tab and
  its panel, and the School tab icon, are INSIGHTS (analytics).
- Navigation icons sit in a 36px tinted circle (`.icon-chip`); product badge
  (`.product-badge`) beside the wordmark replaces the detached brand dot.
- Status colours become text-safe shades (success `#15803D`, warning
  `#B45309`, danger `#B91C1C`) with tints, and always carry a word label.
  Log out stays neutral grey (red already means "struggling").
- The login screen is shared, so it uses the default (LEARN) accent.

## Consequences
- Supersedes ADR-012's dark palette. `tokens.css` is still the single source.
- Future CONNECT/INSIGHTS screens only need the `data-product` attribute.
