/* ADR-051: directors add Console staff, change roles, and handle lost phones. */
import { useState } from "react";
import { Copy, Plus } from "lucide-react";
import { call } from "./api";
import { when } from "./format";
import { Banner } from "./shared";
import { useLoad } from "./useLoad";

function TempPassword({ who, password, onDone }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="credentials" role="status">
      <h3>Temporary password for {who}</h3>
      <p>
        <code>{password}</code>
      </p>
      <p className="muted">Shown once. Give it to them in person or by phone. They set up the authenticator app and their own password at first sign-in.</p>
      <div className="row">
        <button
          type="button"
          className="btn"
          onClick={async () => {
            try {
              await navigator.clipboard.writeText(password);
              setCopied(true);
            } catch {
              setCopied(false);
            }
          }}
        >
          <Copy size={16} aria-hidden="true" /> {copied ? "Copied" : "Copy"}
        </button>
        <button type="button" className="btn btn--ghost" onClick={onDone}>Done</button>
      </div>
    </div>
  );
}

export default function Staff({ token, me }) {
  const { data, error, reload } = useLoad("/staff", token);
  const [f, setF] = useState({ email: "", display_name: "", role: "agent" });
  const [temp, setTemp] = useState(null);
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);

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
  const roles = data?.roles || [];

  return (
    <div className="two-col">
      <section className="stack">
        <Banner>{error || err}</Banner>
        {temp && <TempPassword {...temp} onDone={() => setTemp(null)} />}
        <table className="table">
          <thead>
            <tr><th>Name</th><th>Email</th><th>Role</th><th>Authenticator</th><th>Last sign-in</th><th><span className="sr-only">Actions</span></th></tr>
          </thead>
          <tbody>
            {data?.staff.map((s) => {
              const self = s.id === me.id;
              return (
                <tr key={s.id} className={s.active ? "" : "row--off"}>
                  <td>{s.display_name}{self ? " (you)" : ""}{!s.active ? " · switched off" : ""}</td>
                  <td>{s.email}</td>
                  <td>
                    <label className="sr-only" htmlFor={`role-${s.id}`}>Role for {s.display_name}</label>
                    <select
                      id={`role-${s.id}`}
                      value={s.role}
                      disabled={self || busy}
                      onChange={(e) => run(() => call(`/staff/${s.id}`, { token, method: "POST", body: { role: e.target.value } }))}
                    >
                      {roles.map((r) => (
                        <option key={r.id} value={r.id}>{r.label}</option>
                      ))}
                    </select>
                  </td>
                  <td>{s.authenticator_set_up ? "Set up" : "Not yet"}</td>
                  <td className="nowrap">{when(s.last_login_at)}</td>
                  <td className="actions">
                    {!self && (
                      <>
                        <button type="button" className="btn btn--small btn--ghost" disabled={busy}
                          onClick={() => run(() => call(`/staff/${s.id}/reset-authenticator`, { token, method: "POST" }))}>
                          Lost phone
                        </button>
                        <button type="button" className="btn btn--small btn--ghost" disabled={busy}
                          onClick={() => run(async () => {
                            const r = await call(`/staff/${s.id}/reset-password`, { token, method: "POST" });
                            setTemp({ who: s.display_name, password: r.temp_password });
                          })}>
                          Reset password
                        </button>
                        <button type="button" className="btn btn--small btn--ghost" disabled={busy}
                          onClick={() => run(() => call(`/staff/${s.id}`, { token, method: "POST", body: { active: !s.active } }))}>
                          {s.active ? "Switch off" : "Switch on"}
                        </button>
                      </>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        <dl className="roles-help">
          <dt>Support agent</dt><dd>Tickets; looks up schools (read only).</dd>
          <dt>Support lead</dt><dd>Also registrations, setting up schools, principals, officials, and the audit log.</dd>
          <dt>Director</dt><dd>Also Console staff. Keep at least two directors so one can help the other.</dd>
        </dl>
      </section>
      <aside>
        <form
          className="form card"
          onSubmit={(e) => {
            e.preventDefault();
            run(async () => {
              const r = await call("/staff", { token, method: "POST", body: f });
              setTemp({ who: r.staff.display_name, password: r.temp_password });
              setF({ email: "", display_name: "", role: "agent" });
            });
          }}
        >
          <h2>Add Console staff</h2>
          <label>
            Name
            <input value={f.display_name} onChange={(e) => setF({ ...f, display_name: e.target.value })} required minLength={2} />
          </label>
          <label>
            Work email
            <input type="email" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} required />
          </label>
          <label>
            Role
            <select value={f.role} onChange={(e) => setF({ ...f, role: e.target.value })}>
              {roles.map((r) => (
                <option key={r.id} value={r.id}>{r.label}</option>
              ))}
            </select>
          </label>
          <button className="btn btn--primary" disabled={busy}>
            <Plus size={16} aria-hidden="true" /> Add
          </button>
        </form>
      </aside>
    </div>
  );
}
