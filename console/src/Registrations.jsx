/*
 * ADR-051: "Register your school" requests. Replaces
 * `python -m scripts.manage_registrations`. Approve only after phoning the
 * school on its official number and checking the EMIS number.
 */
import { useState } from "react";
import { Check, X } from "lucide-react";
import { call } from "./api";
import { when } from "./format";
import { Banner, Chips, OneTimeCredentials } from "./shared";
import { useLoad } from "./useLoad";

export default function Registrations({ token }) {
  const { data, error, reload } = useLoad("/registrations", token);
  const [filter, setFilter] = useState("pending");
  const [open, setOpen] = useState(null);
  const [asRole, setAsRole] = useState("principal");
  const [checked, setChecked] = useState(false);
  const [cred, setCred] = useState(null);
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);

  const rows = (data?.registrations || []).filter((r) => filter === "all" || r.status === filter);
  const act = async (r, what) => {
    setBusy(true);
    setErr(null);
    try {
      const res = await call(`/registrations/${r.id}/${what}`, { token, method: "POST", body: what === "approve" ? { as_role: asRole } : undefined });
      if (res.credentials) setCred(res.credentials);
      setOpen(null);
      setChecked(false);
      await reload();
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="stack">
      <Chips
        label="Request status"
        value={filter}
        onChange={setFilter}
        options={[["pending", "Waiting"], ["approved", "Approved"], ["rejected", "Rejected"], ["all", "All"]]}
      />
      <Banner>{error || err}</Banner>
      <OneTimeCredentials cred={cred} onDone={() => setCred(null)} />
      {data && rows.length === 0 && <p className="muted">Nothing here.</p>}
      {rows.map((r) => (
        <article key={r.id} className="card">
          <header className="row row--between">
            <h2>{r.school_name}</h2>
            <span className={`pill pill--reg-${r.status}`}>{r.status}</span>
          </header>
          <p className="muted">
            Ref {r.reference} · received {when(r.created_at)} · {r.province} · EMIS {r.emis_number || "—"} · about {r.learner_estimate || "?"} learners
          </p>
          <p>
            {r.contact_name}, {r.contact_role} · <a href={`tel:${r.contact_cellphone.replace(/\s/g, "")}`}>{r.contact_cellphone}</a>
            {r.contact_email ? ` · ${r.contact_email}` : ""}
          </p>
          {r.message && <blockquote>{r.message}</blockquote>}
          {r.status === "pending" && open !== r.id && (
            <div className="row">
              <button type="button" className="btn btn--primary" onClick={() => { setOpen(r.id); setChecked(false); }}>
                <Check size={16} aria-hidden="true" /> Approve…
              </button>
              <button type="button" className="btn btn--ghost" disabled={busy} onClick={() => act(r, "reject")}>
                <X size={16} aria-hidden="true" /> Reject
              </button>
            </div>
          )}
          {open === r.id && (
            <div className="form">
              <label className="check">
                <input type="checkbox" checked={checked} onChange={(e) => setChecked(e.target.checked)} />
                I phoned the school on its official number and checked the EMIS number.
              </label>
              <label>
                {r.contact_name} gets the role
                <select value={asRole} onChange={(e) => setAsRole(e.target.value)}>
                  <option value="principal">Principal</option>
                  <option value="school_admin">School admin (add the principal later under Schools)</option>
                </select>
              </label>
              <div className="row">
                <button type="button" className="btn btn--primary" disabled={!checked || busy} onClick={() => act(r, "approve")}>
                  Approve and create the login
                </button>
                <button type="button" className="btn btn--ghost" onClick={() => setOpen(null)}>
                  Cancel
                </button>
              </div>
            </div>
          )}
        </article>
      ))}
    </div>
  );
}
