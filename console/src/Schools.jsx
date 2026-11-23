/*
 * ADR-051: find a school; see its profile, counts and management team.
 * Leads can set up a school and change its principal. No learner names,
 * marks or work are ever shown here.
 */
import { useState } from "react";
import { Plus, Search, UserMinus, UserPlus } from "lucide-react";
import { call } from "./api";
import { can, when } from "./format";
import { Banner, OneTimeCredentials } from "./shared";
import { useLoad } from "./useLoad";

function NewSchool({ token, onCreated }) {
  const [f, setF] = useState({ name: "", emis_number: "", province: "", email: "", principal_name: "", first_role: "principal" });
  const [err, setErr] = useState(null);
  const [cred, setCred] = useState(null);
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      const r = await call("/schools", { token, method: "POST", body: { ...f, emis_number: f.emis_number || null, province: f.province || null, email: f.email || null } });
      setCred(r.credentials);
      onCreated(r.school_id);
    } catch (e2) {
      setErr(e2.message);
    } finally {
      setBusy(false);
    }
  };
  if (cred) return <OneTimeCredentials cred={cred} />;
  return (
    <form className="form card" onSubmit={submit}>
      <h2>Set up a school</h2>
      <p className="muted">Only under a signed agreement (e.g. a pilot). Schools that applied online are under Registrations.</p>
      <Banner>{err}</Banner>
      <div className="grid2">
        <label>
          School name
          <input value={f.name} onChange={set("name")} required minLength={2} />
        </label>
        <label>
          EMIS number
          <input value={f.emis_number} onChange={set("emis_number")} inputMode="numeric" />
        </label>
        <label>
          Province
          <input value={f.province} onChange={set("province")} />
        </label>
        <label>
          School email
          <input type="email" value={f.email} onChange={set("email")} />
        </label>
        <label>
          First login: name
          <input value={f.principal_name} onChange={set("principal_name")} required minLength={2} />
        </label>
        <label>
          First login: role
          <select value={f.first_role} onChange={set("first_role")}>
            <option value="principal">Principal</option>
            <option value="school_admin">School admin</option>
          </select>
        </label>
      </div>
      <button className="btn btn--primary" disabled={busy}>
        <Plus size={16} aria-hidden="true" /> Set up school
      </button>
    </form>
  );
}

function SchoolDetail({ token, me, id }) {
  const { data: s, error, reload } = useLoad(`/schools/${id}`, token);
  const [mode, setMode] = useState(null); // "existing" | "new"
  const [pick, setPick] = useState("");
  const [name, setName] = useState("");
  const [cred, setCred] = useState(null);
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);
  const lead = can(me, "lead");

  const run = async (fn) => {
    setBusy(true);
    setErr(null);
    try {
      await fn();
      await reload();
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };
  const addPrincipal = (e) => {
    e.preventDefault();
    run(async () => {
      const body = mode === "existing" ? { existing_user_id: pick } : { display_name: name };
      const r = await call(`/schools/${id}/principal`, { token, method: "POST", body });
      setCred(r.credentials);
      setMode(null);
      setName("");
      setPick("");
    });
  };
  const [removing, setRemoving] = useState(null);
  const removePrincipal = (t, off) =>
    run(async () => {
      await call(`/schools/${id}/roles/${t.role_id}/remove`, { token, method: "POST", body: { switch_off: off } });
      setRemoving(null);
    });

  if (error) return <Banner>{error}</Banner>;
  if (!s) return <p className="muted">Loading…</p>;
  return (
    <section className="detail" aria-label={s.name}>
      <header className="detail__head">
        <h2>{s.name}</h2>
        <p className="muted">
          EMIS {s.emis_number || "—"} · {s.province || "province not set"} · circuit {s.circuit || "not placed"} · joined {when(s.created_at)}
        </p>
        <div className="stats">
          <div><strong>{s.learners}</strong><span>learners</span></div>
          <div><strong>{s.staff}</strong><span>staff</span></div>
          <div><strong>{s.classes}</strong><span>classes</span></div>
        </div>
        {!s.has_principal && <Banner kind="warn">This school has no active principal.</Banner>}
      </header>

      <h3>Management team</h3>
      <table className="table">
        <thead>
          <tr><th>Name</th><th>Role</th><th>Login</th><th>Status</th>{lead && <th><span className="sr-only">Actions</span></th>}</tr>
        </thead>
        <tbody>
          {s.team.map((t) => (
            <tr key={t.role_id}>
              <td>{t.name}</td>
              <td>{t.role_label}{t.subject ? ` (${t.subject})` : ""}</td>
              <td><code>{t.login}</code></td>
              <td>{t.active ? "Active" : "Switched off"}</td>
              {lead && (
                <td>
                  {t.role === "principal" && (
                    <button type="button" className="btn btn--small btn--ghost" disabled={busy} onClick={() => setRemoving(t)}>
                      <UserMinus size={14} aria-hidden="true" /> Remove role
                    </button>
                  )}
                </td>
              )}
            </tr>
          ))}
          {s.team.length === 0 && (
            <tr><td colSpan={lead ? 5 : 4} className="muted">No management roles yet.</td></tr>
          )}
        </tbody>
      </table>
      {removing && (
        <div className="card confirm" role="group" aria-label="Remove principal role">
          <p>
            Remove the principal role from <strong>{removing.name}</strong>? Only on a written request from the school or the
            department.
          </p>
          <div className="row">
            <button type="button" className="btn" disabled={busy} onClick={() => removePrincipal(removing, false)}>
              Remove role, keep their login
            </button>
            <button type="button" className="btn btn--danger" disabled={busy} onClick={() => removePrincipal(removing, true)}>
              Remove role and switch off login (they've left)
            </button>
            <button type="button" className="btn btn--ghost" onClick={() => setRemoving(null)}>
              Cancel
            </button>
          </div>
        </div>
      )}
      <p className="muted">The school gives and removes deputy, departmental head and school admin roles itself, in ADMIN.</p>
      <Banner>{err}</Banner>
      <OneTimeCredentials cred={cred} onDone={() => setCred(null)} />

      {lead && !mode && (
        <div className="row">
          <button type="button" className="btn" onClick={() => setMode("existing")} disabled={s.staff_list.length === 0}>
            <UserPlus size={16} aria-hidden="true" /> Make a staff member principal
          </button>
          <button type="button" className="btn" onClick={() => setMode("new")}>
            <Plus size={16} aria-hidden="true" /> New principal login
          </button>
        </div>
      )}
      {lead && mode && (
        <form className="form card" onSubmit={addPrincipal}>
          <p className="muted">Only on a written request from the school or the department.</p>
          {mode === "existing" ? (
            <label>
              Staff member
              <select value={pick} onChange={(e) => setPick(e.target.value)} required>
                <option value="">Choose…</option>
                {s.staff_list.map((u) => (
                  <option key={u.user_id} value={u.user_id}>{u.name} ({u.login})</option>
                ))}
              </select>
            </label>
          ) : (
            <label>
              Principal's name
              <input value={name} onChange={(e) => setName(e.target.value)} required minLength={2} />
            </label>
          )}
          <div className="row">
            <button className="btn btn--primary" disabled={busy}>Add principal</button>
            <button type="button" className="btn btn--ghost" onClick={() => setMode(null)}>Cancel</button>
          </div>
        </form>
      )}

      <h3>Recent support tickets</h3>
      {s.tickets.length === 0 ? (
        <p className="muted">None.</p>
      ) : (
        <ul className="plain">
          {s.tickets.map((t) => (
            <li key={t.number}>#{t.number} {t.subject} · {t.priority_label} · {t.status.replaceAll("_", " ")}</li>
          ))}
        </ul>
      )}
    </section>
  );
}

export default function Schools({ token, me }) {
  const [q, setQ] = useState("");
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState(null);
  const [adding, setAdding] = useState(false);
  const { data, error, reload } = useLoad(`/schools?q=${encodeURIComponent(query)}`, token);

  return (
    <div className="split">
      <section className="list" aria-label="Schools">
        <form className="search" role="search" onSubmit={(e) => { e.preventDefault(); setQuery(q); }}>
          <label className="sr-only" htmlFor="school-q">Search schools</label>
          <input id="school-q" placeholder="Name or EMIS number" value={q} onChange={(e) => setQ(e.target.value)} />
          <button className="btn" aria-label="Search"><Search size={16} aria-hidden="true" /></button>
        </form>
        {can(me, "lead") && (
          <button type="button" className="btn btn--ghost" onClick={() => { setAdding(true); setSelected(null); }}>
            <Plus size={16} aria-hidden="true" /> Set up a school
          </button>
        )}
        <Banner>{error}</Banner>
        <ul className="items">
          {data?.schools.map((s) => (
            <li key={s.id}>
              <button
                type="button"
                className={`item${selected === s.id ? " item--active" : ""}`}
                aria-current={selected === s.id ? "true" : undefined}
                onClick={() => { setSelected(s.id); setAdding(false); }}
              >
                <span className="item__title">{s.name}</span>
                <span className="muted">
                  {s.learners} learners · {s.staff} staff{!s.has_principal ? " · no principal" : ""}
                </span>
              </button>
            </li>
          ))}
        </ul>
        {data && data.schools.length === 0 && <p className="muted">No schools match.</p>}
      </section>
      {adding ? (
        <section className="detail"><NewSchool token={token} onCreated={() => reload()} /></section>
      ) : selected ? (
        <SchoolDetail key={selected} token={token} me={me} id={selected} />
      ) : (
        <section className="detail detail--empty"><p className="muted">Choose a school.</p></section>
      )}
    </div>
  );
}
