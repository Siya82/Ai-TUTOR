// "Principal, Teacher" etc. for a staff header (from GET /school/me).
export function roleSummary(me) {
  if (!me) return "Staff";
  const labels = [...new Set(me.roles.map((r) => r.label))];
  if (me.allocations.length > 0) labels.push("Teacher");
  return labels.length ? labels.join(", ") : "Staff (no classes yet)";
}

// ADR-044: which staff workspace opens first. People who run the school and
// don't teach go to ADMIN; anyone with classes starts in TEACH. A choice made
// with the switcher is remembered on this device.
export const WORKSPACE_KEY = "thutora_staff_workspace";

export function defaultWorkspace(me, stored) {
  if (!me?.can_manage_school) return "teach";
  if (!me.has_academic_access) return "admin";
  if (stored === "teach" || stored === "admin") return stored;
  return me.allocations.length > 0 ? "teach" : "admin";
}

// ADR-051: ADMIN opens where each role's daily work is. Principals and
// deputies run the school, so they land on the Overview. A school admin
// (with no principal or deputy role) does the office work -- learners,
// classes, staff records -- so they land on Learners, with those tabs first.
// Every tab stays available to every manager; the server rules are unchanged.
export const ADMIN_TAB_ORDER = {
  leader: ["overview", "learners", "classes", "staff", "notices", "settings", "activity"],
  office: ["learners", "classes", "staff", "notices", "overview", "settings", "activity"],
};

export function adminFocus(me) {
  const roles = new Set((me?.roles ?? []).map((r) => r.role));
  if (roles.has("principal") || roles.has("deputy_principal")) return "leader";
  return roles.has("school_admin") ? "office" : "leader";
}

export function adminLandingTab(me) {
  return ADMIN_TAB_ORDER[adminFocus(me)][0];
}
