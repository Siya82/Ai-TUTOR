/*
 * NEW 19 Nov 2026 (ADR-038, CONNECT). From a learner's row on the Students
 * tab: give a parent/guardian their own THUTOra login (number + one-time
 * password shown once), link a parent who already has a login (e.g. for a
 * sibling), or unlink one.
 */
import { useEffect, useState } from "react";
import { addLearnerParent, fetchLearnerParents, removeLearnerParent } from "../api";
import GuardianContacts from "./GuardianContacts";

export default function ParentAccessPanel({ token, learner, onClose }) {
  const [parents, setParents] = useState(null);
  const [name, setName] = useState("");
  const [relationship, setRelationship] = useState("Parent");
  const [existing, setExisting] = useState("");
  const [created, setCreated] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = () =>
    fetchLearnerParents(token, learner.learner_id)
      .then(setParents)
      .catch((err) => setError(err.message));

  useEffect(() => {
    const id = setTimeout(load, 0);
    return () => clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [learner.learner_id]);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const result = await addLearnerParent(token, learner.learner_id, {
        display_name: name.trim(),
        relationship_to_learner: relationship,
        existing_login_number: existing.trim() || null,
      });
      setCreated(result);
      setName("");
      setExisting("");
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="admin-result">
      <div className="privacy-notice__header">
        <p className="admin-result__title">Parent access — {learner.display_name}</p>
        <button type="button" className="admin-screen__link-button" onClick={onClose}>
          Close
        </button>
      </div>
      <p className="admin-screen__muted">
        Parents see their child's practice, topics and released marks, and the school's notices — never the child's
        tutor conversations.
      </p>
      <GuardianContacts token={token} learnerId={learner.learner_id} />
      <p className="admin-result__title">Parent logins</p>
      {error && <div className="admin-screen__error">{error}</div>}
      {created?.temp_password && (
        <div className="admin-result">
          <p className="admin-result__title">Login for {created.display_name}</p>
          <dl className="admin-result__details">
            <dt>School</dt>
            <dd>select this school on the login page</dd>
            <dt>Login number</dt>
            <dd>{created.login_number}</dd>
            <dt>One-time password</dt>
            <dd className="admin-result__password">{created.temp_password}</dd>
          </dl>
          <p className="admin-screen__muted">Give this to the parent now; it won't be shown again.</p>
        </div>
      )}
      {parents && parents.length > 0 && (
        <ul className="today-list">
          {parents.map((p) => (
            <li key={p.user_id}>
              <strong>{p.display_name || "Parent"}</strong> ({p.relationship}) · login {p.login_number}
              {p.kind === "viewer" && <span className="consent-badge"> Viewer</span>}
              {!p.is_active && " · deactivated"}{" "}
              <button
                type="button"
                className="admin-screen__link-button"
                onClick={async () => {
                  if (!window.confirm(`Unlink ${p.display_name || "this parent"} from ${learner.display_name}?`)) return;
                  try {
                    await removeLearnerParent(token, learner.learner_id, p.user_id);
                    await load();
                  } catch (err) {
                    setError(err.message);
                  }
                }}
              >
                Unlink
              </button>
            </li>
          ))}
        </ul>
      )}
      <form className="consent-form" onSubmit={submit}>
        <label className="admin-form__field">
          <span>Parent's name</span>
          <input value={name} onChange={(e) => setName(e.target.value)} maxLength={100} disabled={!!existing} />
        </label>
        <label className="admin-form__field">
          <span>Relationship</span>
          <select value={relationship} onChange={(e) => setRelationship(e.target.value)}>
            {["Parent", "Mother", "Father", "Guardian", "Grandparent", "Other"].map((r) => (
              <option key={r}>{r}</option>
            ))}
          </select>
        </label>
        <label className="admin-form__field">
          <span>…or existing parent login</span>
          <input
            value={existing}
            onChange={(e) => setExisting(e.target.value)}
            placeholder="login number"
            maxLength={50}
          />
        </label>
        <button type="submit" disabled={busy || (!name.trim() && !existing.trim())}>
          {existing.trim() ? "Link parent" : "Create parent login"}
        </button>
      </form>
    </div>
  );
}
