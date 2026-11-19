/*
 * NEW 19 Nov 2026 (code review 19 Nov #11). ADMIN → Activity: who did what
 * sensitive thing, and when (password resets, logins switched off, roles,
 * consent, data exports and deletions, mark changes, settings).
 */
import { useEffect, useState } from "react";
import { fetchAuditTrail } from "../api";

function detailText(e) {
  const d = e.details || {};
  if (e.action === "role.grant" || e.action === "role.revoke") return d.role?.replace("_", " ");
  if (e.action === "mark.override") return d.to ? "changed to correct" : "changed to not correct";
  if (e.action === "user.edit")
    return Object.entries(d)
      .map(([k, [a, b]]) => `${k.replace("_", " ")}: ${a ?? "—"} → ${b}`)
      .join("; ");
  if (e.action === "learners.promote") return `${d.promoted} learners`;
  if (e.action === "privacy.delete") return `${d.answers ?? 0} answers, ${d.conversations ?? 0} conversations removed`;
  return "";
}

export default function ActivityLog({ token }) {
  const [events, setEvents] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    fetchAuditTrail(token)
      .then((d) => !cancelled && setEvents(d.events))
      .catch((err) => !cancelled && setError(err.message));
    return () => {
      cancelled = true;
    };
  }, [token]);

  if (error) return <div className="admin-screen__error">{error}</div>;
  if (!events) return <p className="admin-screen__muted">Loading…</p>;
  return (
    <section className="today-card">
      <h3 className="today-card__title">Recent activity</h3>
      <p className="admin-screen__muted">
        A record of sensitive actions at this school, kept for accountability (POPIA). It never includes passwords or
        conversations.
      </p>
      {events.length === 0 ? (
        <p className="admin-screen__muted">Nothing recorded yet.</p>
      ) : (
        <table className="admin-table">
          <thead>
            <tr>
              <th>When</th>
              <th>Who</th>
              <th>What</th>
              <th>About</th>
              <th>Details</th>
            </tr>
          </thead>
          <tbody>
            {events.map((e, i) => (
              <tr key={i}>
                <td>{new Date(e.at.endsWith("Z") ? e.at : `${e.at}Z`).toLocaleString()}</td>
                <td>{e.by}</td>
                <td>{e.label}</td>
                <td>{e.target || "—"}</td>
                <td className="admin-screen__muted">{detailText(e)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
