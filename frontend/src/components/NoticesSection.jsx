/*
 * NEW 19 Nov 2026 (ADR-038, CONNECT). School → Notices: post a notice to
 * parents (whole school or one grade), optionally asking them to confirm
 * they've read it, and see how many have.
 */
import { useEffect, useState } from "react";
import { deleteSchoolNotice, fetchSchoolNotices, postSchoolNotice } from "../api";

export default function NoticesSection({ token }) {
  const [notices, setNotices] = useState(null);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [grade, setGrade] = useState("");
  const [requiresAck, setRequiresAck] = useState(true);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = () =>
    fetchSchoolNotices(token)
      .then(setNotices)
      .catch((err) => setError(err.message));

  useEffect(() => {
    const id = setTimeout(load, 0);
    return () => clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await postSchoolNotice(token, {
        title: title.trim(),
        body: body.trim(),
        grade: grade ? Number(grade) : null,
        requires_ack: requiresAck,
      });
      setTitle("");
      setBody("");
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <form className="admin-form" onSubmit={submit}>
        <label className="admin-form__field">
          <span>Title</span>
          <input value={title} onChange={(e) => setTitle(e.target.value)} maxLength={200} required />
        </label>
        <label className="admin-form__field">
          <span>Message to parents</span>
          <textarea value={body} onChange={(e) => setBody(e.target.value)} rows={4} maxLength={4000} required />
        </label>
        <div className="consent-form">
          <label className="admin-form__field">
            <span>Who</span>
            <select value={grade} onChange={(e) => setGrade(e.target.value)}>
              <option value="">All parents</option>
              {[8, 9, 10, 11, 12].map((g) => (
                <option key={g} value={g}>
                  Grade {g} parents
                </option>
              ))}
            </select>
          </label>
          <label className="admin-form__checkbox-row">
            <input type="checkbox" checked={requiresAck} onChange={(e) => setRequiresAck(e.target.checked)} />
            Ask parents to confirm they've read it
          </label>
          <button type="submit" disabled={busy || !title.trim() || !body.trim()}>
            Post notice
          </button>
        </div>
      </form>
      {error && <div className="admin-screen__error">{error}</div>}
      {notices && notices.length === 0 && <p className="admin-screen__muted">No notices yet.</p>}
      {notices && notices.length > 0 && (
        <table className="admin-table">
          <thead>
            <tr>
              <th>Notice</th>
              <th>To</th>
              <th>Posted</th>
              <th>Read</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {notices.map((n) => (
              <tr key={n.id}>
                <td>
                  <strong>{n.title}</strong>
                  <div className="admin-screen__muted parent-notices__body">{n.body}</div>
                </td>
                <td>{n.grade ? `Grade ${n.grade}` : "All"}</td>
                <td>{n.created_at && new Date(n.created_at).toLocaleDateString()}</td>
                <td>{n.requires_ack ? `${n.acknowledged} of ${n.audience}` : "—"}</td>
                <td>
                  <button
                    type="button"
                    className="admin-screen__link-button"
                    onClick={async () => {
                      if (!window.confirm("Remove this notice for everyone?")) return;
                      try {
                        await deleteSchoolNotice(token, n.id);
                        await load();
                      } catch (err) {
                        setError(err.message);
                      }
                    }}
                  >
                    Remove
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <p className="admin-screen__muted">
        Parents need a login first: on the Students tab, click Parents next to a learner.
      </p>
    </div>
  );
}
