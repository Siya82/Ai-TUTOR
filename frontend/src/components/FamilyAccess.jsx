/*
 * NEW 19 Nov 2026 (ADR-043). A parent/guardian lets someone else in the
 * family (a grandparent, an aunt who helps with homework) see their child's
 * progress. The guardian approves by creating a one-time invite code; the
 * viewer gets their own login, sees progress but not school notices, and
 * can't invite anyone else. The guardian can remove them at any time.
 */
import { useEffect, useState } from "react";
import { fetchViewers, inviteViewer, removeViewer } from "../api";

export default function FamilyAccess({ token, child, schoolName }) {
  const [data, setData] = useState(null);
  const [name, setName] = useState("");
  const [relationship, setRelationship] = useState("Grandmother");
  const [invite, setInvite] = useState(null);
  const [error, setError] = useState(null);

  const load = () =>
    fetchViewers(token, child.learner_id)
      .then(setData)
      .catch((err) => setError(err.message));

  useEffect(() => {
    const id = setTimeout(() => {
      setInvite(null);
      load();
    }, 0);
    return () => clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [child.learner_id]);

  if (child.kind !== "guardian") {
    return (
      <section className="today-card family-access">
        <h3 className="today-card__title">Family access</h3>
        <p className="admin-screen__muted">
          You were invited to see {child.display_name}'s progress. Only a parent or guardian can invite others.
        </p>
      </section>
    );
  }

  const submit = async (e) => {
    e.preventDefault();
    setError(null);
    try {
      const result = await inviteViewer(token, child.learner_id, { viewerName: name.trim(), relationship });
      setInvite({ ...result, name: name.trim() });
      setName("");
      await load();
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <section className="today-card family-access">
      <h3 className="today-card__title">Family access</h3>
      <p className="admin-screen__muted">
        Let a grandparent or another family member see {child.display_name}'s progress. They won't see school
        notices or the tutor conversations, and you can remove them at any time.
      </p>
      {error && <div className="admin-screen__error">{error}</div>}
      {invite && (
        <div className="admin-result">
          <p className="admin-result__title">Invite code for {invite.name}</p>
          <p className="admin-result__password">{invite.code}</p>
          <p className="admin-screen__muted">
            Send them this code. On the THUTOra login page they choose “{schoolName}”, tap “Have an invite code?”
            and enter it. It works once and expires in {invite.expires_in_days} days.
          </p>
        </div>
      )}
      {data && (data.viewers.length > 0 || data.pending_invites.length > 0) && (
        <ul className="today-list">
          {data.viewers.map((v) => (
            <li key={v.user_id}>
              <strong>{v.name}</strong> ({v.relationship}) · login {v.login_number}{" "}
              <button
                type="button"
                className="admin-screen__link-button"
                onClick={async () => {
                  if (!window.confirm(`Stop ${v.name} seeing ${child.display_name}'s progress?`)) return;
                  try {
                    await removeViewer(token, child.learner_id, v.user_id);
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
          {data.pending_invites.map((i, idx) => (
            <li key={`p-${idx}`} className="admin-screen__muted">
              {i.name} ({i.relationship}) · invite not used yet
            </li>
          ))}
        </ul>
      )}
      <form className="consent-form" onSubmit={submit}>
        <label className="admin-form__field">
          <span>Their name</span>
          <input value={name} onChange={(e) => setName(e.target.value)} maxLength={100} required />
        </label>
        <label className="admin-form__field">
          <span>Relationship to {child.display_name}</span>
          <select value={relationship} onChange={(e) => setRelationship(e.target.value)}>
            {["Grandmother", "Grandfather", "Aunt", "Uncle", "Older sibling", "Carer", "Other"].map((r) => (
              <option key={r}>{r}</option>
            ))}
          </select>
        </label>
        <button type="submit" disabled={!name.trim()}>
          Create invite code
        </button>
      </form>
    </section>
  );
}
