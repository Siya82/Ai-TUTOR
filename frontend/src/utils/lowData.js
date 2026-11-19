/*
 * NEW 19 Nov 2026 (ADR-035). "Save data" mode for learners on prepaid data.
 * A per-device setting (kept in this browser only). When on, textbook
 * figures load only when tapped -- equations always load, because the
 * text doesn't make sense without them.
 */
const KEY = "thutora_low_data";

export function isLowData() {
  try {
    return localStorage.getItem(KEY) === "1";
  } catch {
    return false;
  }
}

export function setLowData(on) {
  try {
    localStorage.setItem(KEY, on ? "1" : "0");
  } catch {
    /* storage unavailable: setting just won't persist */
  }
}
