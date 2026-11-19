/*
 * NEW 19 Nov 2026 (code review 19 Nov #7). Change an assignment after it's
 * been issued: title, instructions and due date; close it early (or reopen);
 * duplicate it; delete it while nobody has answered yet.
 */
import { useState } from "react";
import { closeAssignment, deleteAssignment, duplicateAssignment, editAssignment } from "../api";

function toLocalInput(iso) {
  if (!iso) return "";
  const d = new Date(iso.endsWith("Z") ? iso : `${iso}Z`); // stored as UTC
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export default function AssignmentControls({ token, detail, onChanged, onDeleted, onDuplicated }) {
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState(detail.title);
  const [instructions, setInstructions] = useState(detail.instructions || "");
  const [dueAt, setDueAt] = useState(toLocalInput(detail.due_at));
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const run = async (fn) => {
    setBusy(true);
    setError(null);
    try {
      await fn();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const anyAnswered = detail.completions.some((c) => c.answered_count > 0);

  return (
    <div className="assignment-controls">
      <div className="assignment-controls__row">
        <button type="button" className="admin-screen__link-button" onClick={() => setEditing((v) => !v)}>
          {editing ? "Cancel edit" : "Edit / change due date"}
        </button>
        <button
          type="button"
          className="admin-screen__link-button"
          disabled={busy}
          onClick={() =>
            run(async () => {
              await closeAssignment(token, detail.id, detail.closed);
              await onChanged();
            })
          }
        >
          {detail.closed ? "Reopen for answers" : "Close now"}
        </button>
        <button
          type="button"
          className="admin-screen__link-button"
          disabled={busy}
          onClick={() =>
            run(async () => {
              const copy = await duplicateAssignment(token, detail.id);
              await onDuplicated(copy.id);
            })
          }
        >
          Duplicate
        </button>
        <button
          type="button"
          className="admin-screen__link-button"
          disabled={busy || anyAnswered}
          title={anyAnswered ? "Learners have answered — close it instead" : undefined}
          onClick={() => {
            if (!window.confirm(`Delete "${detail.title}"? This can't be undone.`)) return;
            run(async () => {
              await deleteAssignment(token, detail.id);
              await onDeleted();
            });
          }}
        >
          Delete
        </button>
      </div>
      {detail.answers_closed && <p className="admin-screen__muted">{detail.answers_closed}</p>}
      {editing && (
        <form
          className="admin-form"
          onSubmit={(e) => {
            e.preventDefault();
            run(async () => {
              await editAssignment(token, detail.id, { title: title.trim(), instructions, dueAt });
              setEditing(false);
              await onChanged();
            });
          }}
        >
          <label className="admin-form__field">
            <span>Title</span>
            <input value={title} onChange={(e) => setTitle(e.target.value)} maxLength={200} required />
          </label>
          <label className="admin-form__field">
            <span>Instructions</span>
            <textarea value={instructions} onChange={(e) => setInstructions(e.target.value)} rows={3} />
          </label>
          <label className="admin-form__field">
            <span>Due</span>
            <input type="datetime-local" value={dueAt} onChange={(e) => setDueAt(e.target.value)} />
          </label>
          <button type="submit" disabled={busy || !title.trim()}>
            Save
          </button>
        </form>
      )}
      {error && <div className="admin-screen__error">{error}</div>}
    </div>
  );
}
