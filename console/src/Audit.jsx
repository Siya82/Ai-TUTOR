/* ADR-051: every Console action, newest first. */
import { useState } from "react";
import { when } from "./format";
import { Banner } from "./shared";
import { useLoad } from "./useLoad";

function detailText(e) {
  const d = e.details || {};
  const bits = [];
  if (e.target_type === "ticket") bits.push(`ticket #${e.target_id}`);
  if (d.name) bits.push(d.name);
  if (d.area) bits.push(d.area);
  if (d.email) bits.push(d.email);
  if (d.reference) bits.push(`ref ${d.reference}`);
  if (d.from && d.to) bits.push(`${d.from} → ${d.to}`);
  if (d.role) bits.push(d.role.replaceAll("_", " "));
  if (d.switched_off) bits.push("login switched off");
  if (d.via) bits.push(`via ${d.via}`);
  return bits.join(" · ");
}

export default function Audit({ token }) {
  const { data, error } = useLoad("/audit?limit=500", token);
  const [who, setWho] = useState("");
  const people = [...new Set((data?.events || []).map((e) => e.by))].sort();
  const events = (data?.events || []).filter((e) => !who || e.by === who);
  return (
    <div className="stack">
      <div className="row">
        <label className="inline">
          Person
          <select value={who} onChange={(e) => setWho(e.target.value)}>
            <option value="">Everyone</option>
            {people.map((p) => (
              <option key={p}>{p}</option>
            ))}
          </select>
        </label>
        <p className="muted small">Actions on a school also show in that school's ADMIN → Activity, as "THUTOra support".</p>
      </div>
      <Banner>{error}</Banner>
      <table className="table">
        <thead>
          <tr><th>When</th><th>Who</th><th>What</th><th>School</th><th>Details</th></tr>
        </thead>
        <tbody>
          {events.map((e, i) => (
            <tr key={i}>
              <td className="nowrap">{when(e.at)}</td>
              <td>{e.by}</td>
              <td>{e.label}</td>
              <td>{e.school || "—"}</td>
              <td className="muted">{detailText(e)}</td>
            </tr>
          ))}
          {data && events.length === 0 && (
            <tr><td colSpan={5} className="muted">Nothing yet.</td></tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
