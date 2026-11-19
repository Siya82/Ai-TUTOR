/*
 * NEW 19 Nov 2026 (code review 19 Nov #8). Fix a person's name, login
 * number or (learners) grade without recreating the account -- history,
 * marks and parent links stay. School management only (the server checks).
 */
import { useState } from "react";
import { editPerson } from "../api";

export default function EditPerson({ token, person, isLearner, onSaved, onCancel }) {
  const [name, setName] = useState(person.display_name || "");
  const [number, setNumber] = useState(person.login_number || "");
  const [grade, setGrade] = useState(person.grade || 10);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const save = async (e) => {
    e.preventDefault();
    const body = {};
    if (name.trim() && name.trim() !== person.display_name) body.display_name = name.trim();
    if (number.trim() && number.trim() !== person.login_number) body.login_number = number.trim();
    if (isLearner && Number(grade) !== person.grade) {
      if (!window.confirm(`Move ${person.display_name} to Grade ${grade}? They'll leave their Grade ${person.grade} classes.`))
        return;
      body.grade = Number(grade);
    }
    if (Object.keys(body).length === 0) return onCancel();
    setBusy(true);
    setError(null);
    try {
      await editPerson(token, person.user_id, body);
      onSaved();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className="admin-form edit-person" onSubmit={save}>
      <label className="admin-form__field">
        <span>Name</span>
        <input value={name} onChange={(e) => setName(e.target.value)} maxLength={100} required />
      </label>
      <label className="admin-form__field">
        <span>{isLearner ? "Student number" : "Staff number"}</span>
        <input value={number} onChange={(e) => setNumber(e.target.value)} maxLength={50} required />
      </label>
      {isLearner && (
        <label className="admin-form__field">
          <span>Grade</span>
          <select value={grade} onChange={(e) => setGrade(e.target.value)}>
            {[8, 9, 10, 11, 12].map((g) => (
              <option key={g} value={g}>
                Grade {g}
              </option>
            ))}
          </select>
        </label>
      )}
      {error && <div className="admin-screen__error">{error}</div>}
      <div className="edit-person__actions">
        <button type="submit" disabled={busy}>
          Save
        </button>
        <button type="button" className="admin-screen__link-button" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </form>
  );
}
