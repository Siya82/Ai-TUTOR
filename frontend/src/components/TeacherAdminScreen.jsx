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
 * UPDATED 17 Nov 2026 (ADR-030): the dashboard's mastery/risk views
 * (GET /api/v1/dashboard/*), originally left unwired here, now live in
 * the "Progress" tab -- see ProgressPanel.jsx.
 */

import { useEffect, useRef, useState } from "react";
import ProgressPanel from "./ProgressPanel";
import { BarChart3, ClipboardList, LogOut, Sun, Users } from "lucide-react";
import TodayPanel from "./TodayPanel";
import LearnerPrivacyPanel from "./LearnerPrivacyPanel";
import ParentAccessPanel from "./ParentAccessPanel";
import { ICON_BUTTON, ICON_NAV } from "./icons";
import Wordmark from "./Wordmark";
import ChangePassword from "./ChangePassword";
import EditPerson from "./EditPerson";
import AssignmentsPanel from "./AssignmentsPanel"; // deep scan L4: own file
import { roleSummary } from "../utils/staff";
import {
  bulkCreateStudents,
  createStudent,
  fetchAdminStudents,
  fetchSchoolMe,
  resetUserPassword,
  setUserActive,
} from "../api";

// UPDATED 17 Nov 2026 (ADR-031): which tabs show depends on the staff
// member's scope from GET /school/me -- `when` is checked against it.
// The server enforces the same rules; hiding a tab is only convenience.
const TABS = [
  // NEW 19 Nov 2026 (ADR-036): the daily overview comes first for teachers
  { id: "today", label: "Today", icon: Sun, when: (me) => me.has_academic_access },
  { id: "roster", label: "Students", icon: Users, when: () => true },
  { id: "assignments", label: "Assignments", icon: ClipboardList, when: (me) => me.has_academic_access },
  { id: "progress", label: "Progress", icon: BarChart3, product: "insights", when: (me) => me.has_academic_access }, // ADR-030
  // ADR-044: adding learners, bulk upload and School (classes, staff, notices)
  // moved to the ADMIN workspace (AdminScreen.jsx).
];

export default function TeacherAdminScreen({ auth, onLogout, switcher }) {
  const [tab, setTab] = useState("roster");
  const [students, setStudents] = useState([]);
  const [rosterLoading, setRosterLoading] = useState(true);
  const [rosterError, setRosterError] = useState(null);
  const [me, setMe] = useState(null);
  const [meError, setMeError] = useState(null);

  const loadMe = async () => {
    try {
      const loaded = await fetchSchoolMe(auth.token);
      setMe(loaded);
      setMeError(null);
      // ADR-036: open on Today for anyone who teaches (once, on first load)
      if (loaded.has_academic_access) setTab((t) => (t === "roster" ? "today" : t));
    } catch (err) {
      if (err.status === 401) {
        onLogout();
        return;
      }
      setMeError(err.message);
    }
  };

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
    // Code review #17: run the fetch just after the effect (not in its
    // synchronous body) so the loading/error resets don't cascade renders.
    const id = setTimeout(() => {
      loadRoster();
      loadMe();
    }, 0);
    return () => clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const visibleTabs = me ? TABS.filter((t) => t.when(me)) : TABS.filter((t) => t.id === "roster");

  return (
    <div className="admin-screen" data-product="teach">
      <header className="chat-screen__header">
        <Wordmark product="teach" />
        <div className="chat-screen__header-right">
          {switcher}
          <div className="chat-screen__profile">
            <span className="chat-screen__profile-name">
              {me?.display_name ? `${me.display_name} · ` : ""}
              {roleSummary(me)} — {auth.school.name}
            </span>
            <ChangePassword token={auth.token} />
            <button type="button" className="chat-screen__logout" onClick={onLogout}>
              <LogOut size={ICON_BUTTON} aria-hidden="true" />
              Log out
            </button>
          </div>
        </div>
      </header>

      <nav className="admin-screen__tabs">
        {visibleTabs.map((t) => (
          <button
            key={t.id}
            type="button"
            className={`admin-screen__tab${tab === t.id ? " admin-screen__tab--active" : ""}`}
            onClick={() => setTab(t.id)}
            data-product={t.product}
          >
            {/* ADR-034: Progress and School carry INSIGHTS blue; the rest TEACH purple */}
            <span className="icon-chip">
              <t.icon size={ICON_NAV} aria-hidden="true" />
            </span>
            {t.label}
          </button>
        ))}
      </nav>

      <main
        className={`admin-screen__body${
          tab === "progress" || tab === "today" ? " admin-screen__body--wide" : ""
        }`}
      >
        {meError && <div className="admin-screen__error">{meError}</div>}
        {tab === "roster" && (
          <RosterPanel
            token={auth.token}
            onChanged={loadRoster}
            students={students}
            loading={rosterLoading}
            error={rosterError}
            onRetry={loadRoster}
            me={me}
          />
        )}
        {tab === "today" && <TodayPanel token={auth.token} onGoToAssignments={() => setTab("assignments")} />}
        {tab === "progress" && (
          <div data-product="insights">
            <ProgressPanel token={auth.token} onLogout={onLogout} />
          </div>
        )}
        {tab === "assignments" && (
          <AssignmentsPanel token={auth.token} onLogout={onLogout} students={students} me={me} />
        )}
      </main>
    </div>
  );
}

export function RosterPanel({ token, onChanged, students, loading, error, onRetry, me }) {
  // NEW 17 Nov 2026 (code review #13): reset a forgotten password (any
  // teacher, for learners on their roster) and deactivate/reactivate a
  // learner who left (school management only).
  const [busyId, setBusyId] = useState(null);
  const [notice, setNotice] = useState(null);
  const [actionError, setActionError] = useState(null);
  const [privacyFor, setPrivacyFor] = useState(null); // ADR-037
  const [parentsFor, setParentsFor] = useState(null); // ADR-038
  const [editing, setEditing] = useState(null); // code review 19 Nov #8

  const run = async (learner, action) => {
    setBusyId(learner.user_id);
    setActionError(null);
    setNotice(null);
    try {
      if (action === "reset") {
        const result = await resetUserPassword(token, learner.user_id);
        setNotice({ name: learner.display_name, number: learner.student_number, password: result.temp_password });
      } else {
        await setUserActive(token, learner.user_id, action === "reactivate");
        onChanged();
      }
    } catch (err) {
      setActionError(err.message);
    } finally {
      setBusyId(null);
    }
  };

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
        {me && !me.can_manage_school
          ? "No learners to show yet. You'll see learners here once the principal or school admin allocates you a class."
          : "No learners yet — add them in ADMIN → Learners."}
      </p>
    );
  }
  const canManage = Boolean(me?.can_manage_school);
  return (
    <>
      {notice && (
        <div className="admin-result">
          <p className="admin-result__title">New one-time password for {notice.name}</p>
          <dl className="admin-result__details">
            <dt>Student number</dt>
            <dd>{notice.number}</dd>
            <dt>One-time password</dt>
            <dd className="admin-result__password">{notice.password}</dd>
          </dl>
          <p className="admin-screen__muted">
            Give this to the learner now; it won't be shown again. They'll choose their own password when they log in.
          </p>
        </div>
      )}
      {actionError && <div className="admin-screen__error">{actionError}</div>}
      {privacyFor && (
        <LearnerPrivacyPanel
          key={privacyFor.learner_id}
          token={token}
          learner={privacyFor}
          canManage={canManage}
          onClose={() => setPrivacyFor(null)}
          onChanged={onChanged}
        />
      )}
      {parentsFor && (
        <ParentAccessPanel
          key={parentsFor.learner_id}
          token={token}
          learner={parentsFor}
          onClose={() => setParentsFor(null)}
        />
      )}
      {students.some((st) => st.is_active !== false && !st.has_consent) && (
        <p className="admin-screen__muted">
          Learners marked "Not yet" have no parent/guardian consent recorded. Click it to record a signed form.
        </p>
      )}
      {editing && (
        <div className="admin-result">
          <p className="admin-result__title">Edit {editing.display_name}</p>
          <EditPerson
            key={editing.user_id}
            token={token}
            isLearner
            person={{ ...editing, login_number: editing.student_number }}
            onCancel={() => setEditing(null)}
            onSaved={() => {
              setEditing(null);
              onChanged();
            }}
          />
        </div>
      )}
      <table className="admin-table">
        <thead>
          <tr>
            <th>Name</th>
            <th>Grade</th>
            <th>Student number</th>
            <th>Classes</th>
            <th>Consent</th>
            <th>Added</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {students.map((s) => (
            <tr key={s.learner_id} className={s.is_active === false ? "admin-table__row--inactive" : ""}>
              <td>
                {s.display_name}
                {s.is_active === false && <span className="admin-screen__muted"> (deactivated)</span>}
              </td>
              <td>{s.grade}</td>
              <td>{s.student_number}</td>
              <td>{s.classes?.length ? s.classes.join(", ") : <span className="admin-screen__muted">—</span>}</td>
              <td>
                {/* ADR-037: parent/guardian consent status */}
                <button
                  type="button"
                  className={`consent-badge ${s.has_consent ? "consent-badge--yes" : "consent-badge--no"}`}
                  onClick={() => setPrivacyFor(s)}
                  title="Consent and privacy"
                >
                  {s.has_consent ? "Yes" : "Not yet"}
                </button>
              </td>
              <td>{new Date(s.created_at).toLocaleDateString()}</td>
              <td className="admin-table__actions">
                {s.is_active !== false && (
                  <button
                    type="button"
                    className="admin-screen__link-button"
                    disabled={busyId === s.user_id}
                    onClick={() => run(s, "reset")}
                  >
                    Reset password
                  </button>
                )}
                {s.is_active !== false && (
                  <button type="button" className="admin-screen__link-button" onClick={() => setParentsFor(s)}>
                    Parents
                  </button>
                )}
                {canManage && (
                  <button type="button" className="admin-screen__link-button" onClick={() => setEditing(s)}>
                    Edit
                  </button>
                )}
                {canManage && (
                  <button
                    type="button"
                    className="admin-screen__link-button"
                    disabled={busyId === s.user_id}
                    onClick={() => {
                      const leaving = s.is_active !== false;
                      if (
                        leaving &&
                        !window.confirm(`Deactivate ${s.display_name}? They won't be able to log in. Their work is kept.`)
                      )
                        return;
                      run(s, leaving ? "deactivate" : "reactivate");
                    }}
                  >
                    {s.is_active === false ? "Reactivate" : "Deactivate"}
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}

export function AddStudentPanel({ token, onLogout, onCreated }) {
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

export function BulkUploadPanel({ token, onLogout, onCreated }) {
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
