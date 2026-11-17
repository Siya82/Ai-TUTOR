/*
 * NEW 17 Nov 2026: one place for icon sizes, so every screen uses the same
 * scale (Siya's spec, from his tab-icon mockup):
 *   - 24px  navigation (main tabs and view toggles)
 *   - 20px  buttons (log out, attach, ask, modality, sub-tabs)
 *   - 16px  inline actions
 * Icons come from lucide-react; the names match the spec table. They inherit
 * the text colour (currentColor), so active/inactive styling stays in CSS.
 * Decorative icons next to a visible label are aria-hidden; an icon-only
 * button must keep its own aria-label.
 */
export const ICON_NAV = 24;
export const ICON_BUTTON = 20;
export const ICON_INLINE = 16;
