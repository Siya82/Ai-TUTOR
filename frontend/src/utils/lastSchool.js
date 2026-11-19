// NEW 19 Nov 2026 (code review 19 Nov #12): the school this device used last.
export const LAST_SCHOOL_KEY = "thutora_last_school";

export function rememberSchool(school) {
  try {
    localStorage.setItem(LAST_SCHOOL_KEY, JSON.stringify({ id: school.id, name: school.name }));
  } catch {
    /* private browsing: just don't remember */
  }
}

export function recalledSchool() {
  try {
    const s = JSON.parse(localStorage.getItem(LAST_SCHOOL_KEY) || "null");
    return s && s.id && s.name ? s : null;
  } catch {
    return null;
  }
}
