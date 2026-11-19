# ADR-040: THUTOra brand specs in the app

**Date:** 19 Nov 2026 · **Status:** Accepted (Siya's "THUTOra Product Family — Brand Specs")

## Decision
- **Colours:** every value from the spec is a token in `tokens.css`:
  navy `#0F1D3D` (now the app background), white, and primary/light/dark for
  LEARN `#16A34A/#22C55E/#15803D`, TEACH `#7C3AED/#A78BFA/#5B21B6`,
  CONNECT `#F97316/#FDBA74/#EA580C`, INSIGHTS `#2B78DB/#60A5FA/#1D4EDB`.
  On the navy background, text, icon strokes and buttons use the Light shade
  (Primary for CONNECT, whose Light is too pale for text), with navy text on
  coloured buttons and badges. The dark background from ADR-034 stays.
- **Warning status** moves from orange to amber `#FBBF24` so "Watch"/"due"
  warnings never look like CONNECT orange.
- **Marks:** the four product marks were cut from the brand sheet into
  `public/thutora-{learn,teach,connect,insights}-logo.png` (160px, on a white
  rounded tile, as designed). App/install icons use the LEARN mark.
- **Wordmark** (`Wordmark.jsx`): mark + "THUTO" (Poppins Bold; white instead
  of navy, since navy text is invisible on the navy app) + "ra" (SemiBold, in
  the product colour) + the product badge. The login screen shows the
  LEARN-coloured wordmark plus all four marks, since every product shares it.
- **Typography:** Poppins 400/500/600/700, bundled via `@fontsource/poppins`
  (no Google Fonts request: works offline, no extra data, no third-party call).

## Follow-up
The marks are raster cuts from the spec sheet. When the designer supplies
SVG or 1024px PNG originals, replace the files in `frontend/public/` (same
names) for sharper install icons.
