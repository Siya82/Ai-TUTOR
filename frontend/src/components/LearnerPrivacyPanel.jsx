/*
 * NEW 19 Nov 2026 (ADR-037, POPIA basics). Opened from a learner's row on the
 * Students tab: record a parent's/guardian's consent (or its withdrawal), and
 * -- for school management -- download everything held on the learner or
 * delete it all.
 */
import { useEffect, useState } from "react";
import {
  deleteLearnerData,
  downloadLearnerExport,
  fetchConsent,
  recordConsent,
  withdrawConsent,
} from "../api";

const METHODS = [
  ["signed_form", "Signed form"],
  ["parent_portal", "Parent portal"],
  ["other", "Other"],
];

export default function LearnerPrivacyPanel({ token, learner, canManage, onClose, onChanged }) {
  const [records, setRecords] = useState(null);
  const [error, setError] = useState(null);
  const [givenBy, setGivenBy] = useState("");
  const [relationship, setRelationship] = useState("Parent");
  const [method, setMethod] = useState("signed_form");
  const [busy, setBusy] = useState(false);
  const [deleted, setDeleted] = useState(null);

  const load = () =>
    fetchConsent(token, learner.learner_id)
      .then(setRecords)
      .catch((err) => setError(err.message));

  useEffect(() => {
    const id = setTimeout(load, 0);
    return () => clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [learner.learner_id]);

  const act = async (fn) => {
    setBusy(true);
    setError(null);
    try {
      await fn();
      await load();
      onChanged();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const active = (records || []).find((r) => !r.withdrawn_at);

  const handleExport = async () => {
    setBusy(true);
    setError(null);
    try {
      const { blob, fileName } = await downloadLearnerExport(token, learner.learner_id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = fileName;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const handleDelete = async () => {
    const typed = window.prompt(
      `This permanently deletes ${learner.display_name}'s account, chats, answers, uploads and consent records. ` +
        `It cannot be undone. Download their data first if the parent asked for a copy.\n\nType the learner's name to confirm:`
    );
    if (!typed) return;
    setBusy(true);
    setError(null);
    try {
      const result = await deleteLearnerData(token, learner.learner_id, typed);
      setDeleted(result);
      onChanged();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  if (deleted) {
    return (
      <div className="admin-result">
        <p className="admin-result__title">{learner.display_name}'s data was deleted</p>
        <p className="admin-screen__muted">
          Removed {deleted.answers} answers, {deleted.conversations} tutor conversations and {deleted.attachments}{" "}
          uploaded files.
        </p>
        <button type="button" className="admin-screen__link-button" onClick={onClose}>
          Close
        </button>
      </div>
    );
  }

  return (
    <div className="admin-result">
      <div className="privacy-notice__header">
        <p className="admin-result__title">Privacy — {learner.display_name}</p>
        <button type="button" className="admin-screen__link-button" onClick={onClose}>
          Close
        </button>
      </div>
      {error && <div className="admin-screen__error">{error}</div>}
      {records === null ? (
        <p className="admin-screen__muted">Loading…</p>
      ) : active ? (
        <p>
          <span className="consent-badge consent-badge--yes">Consent on record</span> from {active.given_by_name} (
          {active.relationship_to_learner}), {new Date(active.recorded_at).toLocaleDateString()}.{" "}
          <button
            type="button"
            className="admin-screen__link-button"
            disabled={busy}
            onClick={() => {
              if (window.confirm("Record that the parent/guardian withdrew consent?")) {
                act(() => withdrawConsent(token, learner.learner_id));
              }
            }}
          >
            Record withdrawal
          </button>
        </p>
      ) : (
        <>
          <p className="admin-screen__muted">
            No parent/guardian consent recorded{records.length ? " (it was withdrawn)" : ""}. Record it once the school has
            the signed form.
          </p>
          <form
            className="consent-form"
            onSubmit={(e) => {
              e.preventDefault();
              if (!givenBy.trim()) return;
              act(() =>
                recordConsent(token, learner.learner_id, { givenByName: givenBy.trim(), relationship, method })
              ).then(() => setGivenBy(""));
            }}
          >
            <label className="admin-form__field">
              <span>Given by (name)</span>
              <input value={givenBy} onChange={(e) => setGivenBy(e.target.value)} maxLength={100} required />
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
              <span>How</span>
              <select value={method} onChange={(e) => setMethod(e.target.value)}>
                {METHODS.map(([v, l]) => (
                  <option key={v} value={v}>
                    {l}
                  </option>
                ))}
              </select>
            </label>
            <button type="submit" disabled={busy}>
              Record consent
            </button>
          </form>
        </>
      )}
      {canManage && (
        <p className="admin-table__actions">
          <button type="button" className="admin-screen__link-button" disabled={busy} onClick={handleExport}>
            Download all data
          </button>
          <button type="button" className="admin-screen__link-button" disabled={busy} onClick={handleDelete}>
            Delete learner and all data
          </button>
        </p>
      )}
    </div>
  );
}
