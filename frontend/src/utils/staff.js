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
