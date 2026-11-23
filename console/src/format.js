// Small display helpers (unit-tested).
export const RANK = { agent: 0, lead: 1, director: 2 };

export function can(me, minimum) {
  return !!me && (RANK[me.role] ?? -1) >= RANK[minimum];
}

export function ago(iso, now = Date.now()) {
  if (!iso) return "—";
  const mins = Math.max(0, Math.round((now - new Date(iso + (iso.endsWith("Z") ? "" : "Z")).getTime()) / 60000));
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins} min ago`;
  const h = Math.floor(mins / 60);
  if (h < 48) return `${h} h ago`;
  return `${Math.floor(h / 24)} days ago`;
}

export function when(iso) {
  if (!iso) return "—";
  const d = new Date(iso + (iso.endsWith("Z") ? "" : "Z"));
  return d.toLocaleString("en-ZA", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}

export const STATUS_LABEL = {
  open: "Waiting for Zynora",
  waiting_on_school: "Waiting on school",
  resolved: "Resolved",
};
