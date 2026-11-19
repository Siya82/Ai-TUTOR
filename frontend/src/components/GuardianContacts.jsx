/*
 * NEW 19 Nov 2026 (ADR-043). The parent/guardian contacts the SCHOOL holds
 * for a learner (from enrolment forms or SA-SAMS). A parent can only sign
 * themselves up with a cellphone number that appears here -- that match is
 * the proof they are the learner's parent or guardian.
 */
import { useEffect, useState } from "react";
import { addGuardian, fetchGuardians, removeGuardian, updateGuardian } from "../api";

const RELATIONSHIPS = ["Mother", "Father", "Parent", "Guardian", "Grandparent", "Foster parent", "Other"];
const EMPTY = { full_name: "", relationship_to_learner: "Mother", cellphone: "", email: "" };

export default function GuardianContacts({ token, learnerId }) {
  const [rows, setRows] = useState(null);
  const [form, setForm] = useState(EMPTY);
  const [editingId, setEditingId] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = () =>
    fetchGuardians(token, learnerId)
      .then(setRows)
      .catch((err) => setError(err.message));

  useEffect(() => {
    const id = setTimeout(load, 0);
    return () => clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [learnerId]);

  const save = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const body = { ...form, cellphone: form.cellphone.trim() || null, email: form.email.trim() || null };
      if (editingId) await updateGuardian(token, learnerId, editingId, body);
      else await addGuardian(token, learnerId, body);
      setForm(EMPTY);
      setEditingId(null);
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  return (
    <div className="guardian-contacts">
      <p className="admin-result__title">Guardian contacts on record</p>
      <p className="admin-screen__muted">
        A parent can sign themselves up only with a cellphone number listed here, so keep these as on the
        enrolment form.
      </p>
      {error && <div className="admin-screen__error">{error}</div>}
      {rows && rows.length === 0 && <p className="admin-screen__muted">No contacts recorded yet.</p>}
      {rows && rows.length > 0 && (
        <ul className="today-list">
          {rows.map((g) => (
            <li key={g.id}>
              <strong>{g.full_name}</strong> ({g.relationship}){g.cellphone && ` · ${g.cellphone}`}
              {g.email && ` · ${g.email}`}{" "}
              {g.signed_up ? (
                <span className="consent-badge consent-badge--yes">Signed up</span>
              ) : (
                <span className="consent-badge">Not signed up</span>
              )}{" "}
              <button
                type="button"
                className="admin-screen__link-button"
                onClick={() => {
                  setEditingId(g.id);
                  setForm({
                    full_name: g.full_name,
                    relationship_to_learner: g.relationship,
                    cellphone: g.cellphone || "",
                    email: g.email || "",
                  });
                }}
              >
                Edit
              </button>{" "}
              <button
                type="button"
                className="admin-screen__link-button"
                onClick={async () => {
                  if (!window.confirm(`Remove ${g.full_name} from this learner's contacts?`)) return;
                  try {
                    await removeGuardian(token, learnerId, g.id);
                    await load();
                  } catch (err) {
                    setError(err.message);
                  }
                }}
              >
                Remove
              </button>
            </li>
          ))}
        </ul>
      )}
      <form className="consent-form" onSubmit={save}>
        <label className="admin-form__field">
          <span>Name</span>
          <input value={form.full_name} onChange={set("full_name")} maxLength={100} required />
        </label>
        <label className="admin-form__field">
          <span>Relationship</span>
          <select value={form.relationship_to_learner} onChange={set("relationship_to_learner")}>
            {RELATIONSHIPS.map((r) => (
              <option key={r}>{r}</option>
            ))}
          </select>
        </label>
        <label className="admin-form__field">
          <span>Cellphone</span>
          <input value={form.cellphone} onChange={set("cellphone")} placeholder="082 123 4567" maxLength={30} />
        </label>
        <label className="admin-form__field">
          <span>Email (optional)</span>
          <input type="email" value={form.email} onChange={set("email")} maxLength={200} />
        </label>
        <button type="submit" disabled={busy || !form.full_name.trim()}>
          {editingId ? "Save contact" : "Add contact"}
        </button>
        {editingId && (
          <button
            type="button"
            className="admin-screen__link-button"
            onClick={() => {
              setEditingId(null);
              setForm(EMPTY);
            }}
          >
            Cancel
          </button>
        )}
      </form>
    </div>
  );
}
