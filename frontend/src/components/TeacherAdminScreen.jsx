/*
 * NEW 15 Nov 2026 (ADR-024, teacher dashboard access + bulk student
 * provisioning). The screen App.jsx renders for a teacher-role login
 * instead of ChatScreen -- this is the real replacement for "the only
 * way to add a student is to re-run scripts/seed_dev_data.py", a gap
 * flagged as open since ADR-017.
 *
 * Deliberately a full admin page rather than a single endpoint with no
 * UI (Siya's explicit choice, via AskUserQuestion): a teacher adds one
 * student via a form, or many at once via a CSV upload, and sees the
 * resulting temp passwords -- the ONE time they're ever shown, same
 * posture as provision_student()/provision_teacher() -- right there
 * rather than needing a second tool to read them out of a database.
 *
 * Deliberately NOT built here (see docs/ADR-024...): the teacher
 * dashboard's own learner mastery/risk views (GET /api/v1/dashboard/*)
 * -- this screen only covers the "add/see my students" half of the
 * gap this session was asked to close; wiring the existing dashboard
 * data into this UI is a natural next step, not done in this pass.
 */

import { useEffect, useRef, useState } from "react";
import { bulkCreateStudents, createStudent, fetchAdminStudents } from "../api";

const TABS = [
  { id: "roster", label: "Students" },
  { id: "add", label: "Add student" },
  { id: "bulk", label: "Bulk upload" },
];

export default function TeacherAdminScreen({ auth, onLogout }) {
  const [tab, setTab] = useState("roster");
  const [students, setStudents] = useState([]);
  const [rosterLoading, setRosterLoading] = useState(true);
  const [rosterError, setRosterError] = useState(null);

  const loadRoster = async () => {
    setRosterLoading(true);
    setRosterError(null);
    try {
      const list = await fetchAdminStudents(auth.token);
      setStudents(list);
    } catch (err) {
      if (err.status === 401) {
        onLogout();
        return;
      }
      setRosterError(err.message);
    } finally {
      setRosterLoading(false);
    }
  };

  useEffect(() => {
    loadRoster();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="admin-screen">
      <header className="chat-screen__header">
        <div className="chat-screen__brand">
          <img src="/thutora-logo.png" alt="" className="chat-screen__brand-logo" />
          THUTOra<span className="chat-screen__brand-dot">.</span>
        </div>
        <div className="chat-screen__header-right">
          <div className="chat-screen__profile">
            <span className="chat-screen__profile-name">{auth.school.name} — Teacher</span>
            <button type="button" className="chat-screen__logout" onClick={onLogout}>
              Log out
            </button>
          </div>
        </div>
      </header>

      <nav className="admin-screen__tabs">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            className={`admin-screen__tab${tab === t.id ? " admin-screen__tab--active" : ""}`}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </nav>

      <main className="admin-screen__body">
        {tab === "roster" && (
          <RosterPanel
            students={students}
            loading={rosterLoading}
            error={rosterError}
            onRetry={loadRoster}
          />
        )}
        {tab === "add" && (
          <AddStudentPanel token={auth.token} onLogout={onLogout} onCreated={loadRoster} />
        )}
        {tab === "bulk" && (
          <BulkUploadPanel token={auth.token} onLogout={onLogout} onCreated={loadRoster} />
        )}
      </main>
    </div>
  );
}

function RosterPanel({ students, loading, error, onRetry }) {
  if (loading) return <p className="admin-screen__muted">Loading students…</p>;
  if (error) {
    return (
      <div className="admin-screen__error">
        {error}{" "}
        <button type="button" className="admin-screen__link-button" onClick={onRetry}>
          Try again
        </button>
      </div>
    );
  }
  if (students.length === 0) {
    return (
      <p className="admin-screen__muted">
        No students yet — add one, or upload a CSV, using the tabs above.
      </p>
    );
  }
  return (
    <table className="admin-table">
      <thead>
        <tr>
          <th>Name</th>
          <th>Grade</th>
          <th>Student number</th>
          <th>Added</th>
        </tr>
      </thead>
      <tbody>
        {students.map((s) => (
          <tr key={s.learner_id}>
            <td>{s.display_name}</td>
            <td>{s.grade}</td>
            <td>{s.student_number}</td>
            <td>{new Date(s.created_at).toLocaleDateString()}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function AddStudentPanel({ token, onLogout, onCreated }) {
  const [displayName, setDisplayName] = useState("");
  const [grade, setGrade] = useState(10);
  const [studentNumber, setStudentNumber] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!displayName.trim() || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      const created = await createStudent({
        token,
        displayName: displayName.trim(),
        grade: Number(grade),
        studentNumber: studentNumber.trim() || undefined,
      });
      setResult(created);
      setDisplayName("");
      setStudentNumber("");
      onCreated();
    } catch (err) {
      if (err.status === 401) {
        onLogout();
        return;
      }
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="admin-panel">
      <form className="admin-form" onSubmit={handleSubmit}>
        <label className="admin-form__field">
          <span>Full name</span>
          <input
            type="text"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            required
            autoFocus
          />
        </label>
        <label className="admin-form__field">
          <span>Grade</span>
          <select value={grade} onChange={(e) => setGrade(e.target.value)}>
            <option value={10}>10</option>
            <option value={11}>11</option>
            <option value={12}>12</option>
          </select>
        </label>
        <label className="admin-form__field">
          <span>Student number (optional — leave blank to auto-generate)</span>
          <input
            type="text"
            value={studentNumber}
            onChange={(e) => setStudentNumber(e.target.value)}
            placeholder="auto-generated if left blank"
          />
        </label>
        {error && <div className="admin-screen__error">{error}</div>}
        <button type="submit" disabled={submitting}>
          {submitting ? "Adding…" : "Add student"}
        </button>
      </form>

      {result && (
        <div className="admin-result">
          <p className="admin-result__title">
            {result.display_name} was added — share these login details with them now
            (the password won't be shown again):
          </p>
          <dl className="admin-result__details">
            <dt>Student number</dt>
            <dd>{result.student_number}</dd>
            <dt>Temporary password</dt>
            <dd className="admin-result__password">{result.temp_password}</dd>
          </dl>
        </div>
      )}
    </div>
  );
}

function BulkUploadPanel({ token, onLogout, onCreated }) {
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const fileInputRef = useRef(null);

  const handleUpload = async (e) => {
    e.preventDefault();
    if (!file || uploading) return;
    setUploading(true);
    setError(null);
    try {
      const response = await bulkCreateStudents({ token, file });
      setResult(response);
      if (response.created.length > 0) onCreated();
      setFile(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
    } catch (err) {
      if (err.status === 401) {
        onLogout();
        return;
      }
      setError(err.message);
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="admin-panel">
      <p className="admin-screen__muted">
        CSV columns: <code>display_name</code>, <code>grade</code>, and an optional{" "}
        <code>student_number</code>. One row per student — a bad row is reported individually and
        doesn't stop the rest from being added.
      </p>
      <form className="admin-form" onSubmit={handleUpload}>
        <input
          ref={fileInputRef}
          type="file"
          accept=".csv,text/csv"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
        />
        {error && <div className="admin-screen__error">{error}</div>}
        <button type="submit" disabled={!file || uploading}>
          {uploading ? "Uploading…" : "Upload CSV"}
        </button>
      </form>

      {result && (
        <div className="admin-result">
          <p className="admin-result__title">
            {result.created.length} student{result.created.length === 1 ? "" : "s"} added
            {result.errors.length > 0 ? `, ${result.errors.length} row(s) had problems:` : "."}
          </p>
          {result.errors.length > 0 && (
            <ul className="admin-errors">
              {result.errors.map((e, i) => (
                <li key={i}>
                  Row {e.row}: {e.message}
                </li>
              ))}
            </ul>
          )}
          {result.created.length > 0 && (
            <table className="admin-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Grade</th>
                  <th>Student number</th>
                  <th>Temporary password</th>
                </tr>
              </thead>
              <tbody>
                {result.created.map((c) => (
                  <tr key={c.user_id}>
                    <td>{c.display_name}</td>
                    <td>{c.grade}</td>
                    <td>{c.student_number}</td>
                    <td className="admin-result__password">{c.temp_password}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {result.created.length > 0 && (
            <p className="admin-screen__muted">
              These passwords won't be shown again — share them with each student now.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
