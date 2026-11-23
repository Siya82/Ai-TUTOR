/*
 * ADR-051: INSIGHTS set-up -- districts, circuits, which schools sit where,
 * and education officials. Replaces `python -m scripts.manage_insights`.
 * Officials are added only under a signed agreement with the department.
 */
import { useState } from "react";
import { Plus, UserMinus } from "lucide-react";
import { call } from "./api";
import { Banner, OneTimeCredentials } from "./shared";
import { useLoad } from "./useLoad";

function OfficialList({ list, onRemove, busy }) {
  if (!list.length) return <p className="muted small">No officials.</p>;
  return (
    <ul className="plain">
      {list.map((o) => (
        <li key={o.user_id} className="row row--between">
          <span>
            {o.name} · <code>{o.login}</code> <span className="muted">({o.office})</span>
          </span>
          <button type="button" className="btn btn--small btn--ghost" disabled={busy} onClick={() => onRemove(o)}>
            <UserMinus size={14} aria-hidden="true" /> Remove
          </button>
        </li>
      ))}
    </ul>
  );
}

export default function Officials({ token }) {
  const { data, error, reload } = useLoad("/insights", token);
  const [err, setErr] = useState(null);
  const [cred, setCred] = useState(null);
  const [busy, setBusy] = useState(false);
  const [district, setDistrict] = useState({ name: "", province: "KwaZulu-Natal" });
  const [circuit, setCircuit] = useState({ district_id: "", name: "" });
  const [official, setOfficial] = useState({ name: "", area: "" });
  const [place, setPlace] = useState({ school: "", circuit: "" });

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
  const remove = (o) => {
    if (window.confirm(`Remove ${o.name}? Their login is switched off at once.`)) {
      run(() => call(`/officials/${o.user_id}/remove`, { token, method: "POST" }));
    }
  };

  const districts = data?.districts || [];
  const circuits = districts.flatMap((d) => d.circuits.map((c) => ({ ...c, district: d.name })));
  const schools = [...(data?.unplaced_schools || []), ...circuits.flatMap((c) => c.schools)].sort((a, b) => a.name.localeCompare(b.name));

  return (
    <div className="two-col">
      <section className="stack" aria-label="Structure">
        <Banner>{error || err}</Banner>
        <OneTimeCredentials cred={cred} onDone={() => setCred(null)} />
        {districts.length === 0 && <p className="muted">No districts yet. Add one on the right.</p>}
        {districts.map((d) => (
          <article key={d.id} className="card">
            <h2>
              {d.name} <span className="muted small">{d.province}</span>
            </h2>
            <h3 className="small">District officials</h3>
            <OfficialList list={d.officials} onRemove={remove} busy={busy} />
            {d.circuits.map((c) => (
              <div key={c.id} className="nested">
                <h3>{c.name}</h3>
                <p className="muted small">Schools: {c.schools.map((s) => s.name).join(", ") || "none yet"}</p>
                <OfficialList list={c.officials} onRemove={remove} busy={busy} />
              </div>
            ))}
          </article>
        ))}
        {data?.unplaced_schools?.length > 0 && (
          <p className="muted small">Not in a circuit yet: {data.unplaced_schools.map((s) => s.name).join(", ")}</p>
        )}
      </section>

      <aside className="stack" aria-label="Add">
        <form
          className="form card"
          onSubmit={(e) => {
            e.preventDefault();
            const area = official.area;
            const body = { name: official.name, ...(area.startsWith("c:") ? { circuit_id: area.slice(2) } : { district_id: area.slice(2) }) };
            run(async () => {
              const r = await call("/officials", { token, method: "POST", body });
              setCred(r.credentials);
              setOfficial({ name: "", area: "" });
            });
          }}
        >
          <h2>Add an education official</h2>
          <p className="muted small">Only under a signed agreement with the department.</p>
          <label>
            Name
            <input value={official.name} onChange={(e) => setOfficial({ ...official, name: e.target.value })} required minLength={2} />
          </label>
          <label>
            Sees
            <select value={official.area} onChange={(e) => setOfficial({ ...official, area: e.target.value })} required>
              <option value="">Choose a circuit or district…</option>
              {districts.map((d) => (
                <optgroup key={d.id} label={d.name}>
                  <option value={`d:${d.id}`}>The whole {d.name} district</option>
                  {d.circuits.map((c) => (
                    <option key={c.id} value={`c:${c.id}`}>{c.name} circuit</option>
                  ))}
                </optgroup>
              ))}
            </select>
          </label>
          <button className="btn btn--primary" disabled={busy}>
            <Plus size={16} aria-hidden="true" /> Add official
          </button>
        </form>

        <form
          className="form card"
          onSubmit={(e) => {
            e.preventDefault();
            run(async () => {
              await call(`/schools/${place.school}/circuit`, { token, method: "POST", body: { circuit_id: place.circuit || null } });
              setPlace({ school: "", circuit: "" });
            });
          }}
        >
          <h2>Place a school in a circuit</h2>
          <label>
            School
            <select value={place.school} onChange={(e) => setPlace({ ...place, school: e.target.value })} required>
              <option value="">Choose…</option>
              {schools.map((s) => (
                <option key={s.id} value={s.id}>{s.name}</option>
              ))}
            </select>
          </label>
          <label>
            Circuit
            <select value={place.circuit} onChange={(e) => setPlace({ ...place, circuit: e.target.value })}>
              <option value="">No circuit</option>
              {circuits.map((c) => (
                <option key={c.id} value={c.id}>{c.name} ({c.district})</option>
              ))}
            </select>
          </label>
          <button className="btn" disabled={busy}>Save</button>
        </form>

        <form
          className="form card"
          onSubmit={(e) => {
            e.preventDefault();
            run(async () => {
              await call("/circuits", { token, method: "POST", body: circuit });
              setCircuit({ district_id: "", name: "" });
            });
          }}
        >
          <h2>Add a circuit</h2>
          <label>
            District
            <select value={circuit.district_id} onChange={(e) => setCircuit({ ...circuit, district_id: e.target.value })} required>
              <option value="">Choose…</option>
              {districts.map((d) => (
                <option key={d.id} value={d.id}>{d.name}</option>
              ))}
            </select>
          </label>
          <label>
            Circuit name
            <input value={circuit.name} onChange={(e) => setCircuit({ ...circuit, name: e.target.value })} required minLength={2} />
          </label>
          <button className="btn" disabled={busy}>Add circuit</button>
        </form>

        <form
          className="form card"
          onSubmit={(e) => {
            e.preventDefault();
            run(async () => {
              await call("/districts", { token, method: "POST", body: district });
              setDistrict({ name: "", province: district.province });
            });
          }}
        >
          <h2>Add a district</h2>
          <label>
            District name
            <input value={district.name} onChange={(e) => setDistrict({ ...district, name: e.target.value })} required minLength={2} />
          </label>
          <label>
            Province
            <input value={district.province} onChange={(e) => setDistrict({ ...district, province: e.target.value })} required />
          </label>
          <button className="btn" disabled={busy}>Add district</button>
        </form>
      </aside>
    </div>
  );
}
