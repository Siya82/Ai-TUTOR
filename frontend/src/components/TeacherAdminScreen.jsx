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
import {
  bulkCreateStudents,
  createAssignment,
  createCustomQuestion,
  createStudent,
  fetchAdminStudents,
  fetchSubjects,
  fetchTeachAssignment,
  fetchTeachAssignments,
  fetchTopics,
} from "../api";

const TABS = [
  { id: "roster", label: "Students" },
  { id: "add", label: "Add student" },
  { id: "bulk", label: "Bulk upload" },
  { id: "assignments", label: "Assignments" },
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
          <img src="/thutora-teach-logo.png" alt="" className="chat-screen__brand-logo" />
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
        {tab === "assignments" && (
          <AssignmentsPanel token={auth.token} onLogout={onLogout} students={students} />
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

function AssignmentsPanel({ token, onLogout, students }) {
  const [assignments, setAssignments] = useState([]);
  const [listLoading, setListLoading] = useState(true);
  const [listError, setListError] = useState(null);
  const [selected, setSelected] = useState(null);
  const [detail, setDetail] = useState(null);
  const [detailError, setDetailError] = useState(null);

  const loadAssignments = async () => {
    setListLoading(true);
    setListError(null);
    try {
      const list = await fetchTeachAssignments(token);
      setAssignments(list);
    } catch (err) {
      if (err.status === 401) {
        onLogout();
        return;
      }
      setListError(err.message);
    } finally {
      setListLoading(false);
    }
  };

  useEffect(() => {
    loadAssignments();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const openDetail = async (id) => {
    setSelected(id);
    setDetail(null);
    setDetailError(null);
    try {
      const d = await fetchTeachAssignment(token, id);
      setDetail(d);
    } catch (err) {
      if (err.status === 401) {
        onLogout();
        return;
      }
      setDetailError(err.message);
    }
  };

  return (
    <div className="admin-panel">
      <CreateAssignmentForm
        token={token}
        onLogout={onLogout}
        students={students}
        onCreated={loadAssignments}
      />

      <h3 className="admin-screen__subheading">My assignments</h3>
      {listLoading && <p className="admin-screen__muted">Loading assignments…</p>}
      {listError && (
        <div className="admin-screen__error">
          {listError}{" "}
          <button type="button" className="admin-screen__link-button" onClick={loadAssignments}>
            Try again
          </button>
        </div>
      )}
      {!listLoading && !listError && assignments.length === 0 && (
        <p className="admin-screen__muted">No assignments yet — create one above.</p>
      )}
      {!listLoading && !listError && assignments.length > 0 && (
        <table className="admin-table">
          <thead>
            <tr>
              <th>Title</th>
              <th>Due</th>
              <th>Questions</th>
              <th>Students</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {assignments.map((a) => (
              <tr key={a.id}>
                <td>{a.title}</td>
                <td>{a.due_at ? new Date(a.due_at).toLocaleDateString() : "—"}</td>
                <td>{a.question_count}</td>
                <td>{a.target_count}</td>
                <td>
                  <button
                    type="button"
                    className="admin-screen__link-button"
                    onClick={() => openDetail(a.id)}
                  >
                    View
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {selected && (
        <div className="admin-result">
          {detailError && <div className="admin-screen__error">{detailError}</div>}
          {detail && (
            <>
              <p className="admin-result__title">{detail.title} — completion</p>
              <table className="admin-table">
                <thead>
                  <tr>
                    <th>Student</th>
                    <th>Status</th>
                    <th>Answered</th>
                    <th>Correct</th>
                  </tr>
                </thead>
                <tbody>
                  {detail.completions.map((c) => (
                    <tr key={c.learner_id}>
                      <td>{c.display_name}</td>
                      <td>{c.status.replace("_", " ")}</td>
                      <td>
                        {c.answered_count} / {c.question_count}
                      </td>
                      <td>{c.correct_count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
        </div>
      )}
    </div>
  );
}

function CreateAssignmentForm({ token, onLogout, students, onCreated }) {
  const [title, setTitle] = useState("");
  const [instructions, setInstructions] = useState("");
  const [dueAt, setDueAt] = useState("");
  const [selectedLearnerIds, setSelectedLearnerIds] = useState([]);

  // One pending custom question being authored right now (text/model
  // answer/topic) plus the list of questions already created and
  // attached to this not-yet-submitted assignment. ADR-028 deliberately
  // keeps this to teacher-authored custom questions only, for now --
  // there's no endpoint to browse the existing seeded CAPS question
  // bank, so reusing it isn't offered here yet.
  // Cascading Grade -> Subject -> Topic picker (NEW 15 Nov 2026, live-test
  // follow-up): a teacher may teach more than one grade, and the flat
  // unfiltered Topic dropdown this replaced (every topic across every
  // subject and grade, alphabetically-ish by fetch order) made it easy
  // to pick the wrong one by mistake. Grade is hardcoded 10/11/12 (same
  // convention the "Add student" form above already uses) since subject
  // data alone doesn't need to be loaded just to know CAPS' own grade
  // range; Subject and Topic are each filtered client-side from the one
  // unfiltered fetchSubjects()/fetchTopics() call every teacher is
  // allowed (ADR-026 follow-up fix, same day) rather than three separate
  // network round-trips.
  const [grade, setGrade] = useState("");
  const [subjectId, setSubjectId] = useState("");
  const [topicId, setTopicId] = useState("");
  const [questionText, setQuestionText] = useState("");
  const [modelAnswer, setModelAnswer] = useState("");
  const [addingQuestion, setAddingQuestion] = useState(false);
  const [questionError, setQuestionError] = useState(null);
  const [draftQuestions, setDraftQuestions] = useState([]); // [{id, text}]

  const [subjects, setSubjects] = useState([]);
  const [subjectsError, setSubjectsError] = useState(null);
  const [topics, setTopics] = useState([]);
  const [topicsError, setTopicsError] = useState(null);

  useEffect(() => {
    fetchSubjects(token)
      .then(setSubjects)
      .catch((err) => {
        if (err.status === 401) {
          onLogout();
          return;
        }
        setSubjectsError(err.message);
      });
    fetchTopics(token)
      .then(setTopics)
      .catch((err) => {
        if (err.status === 401) {
          onLogout();
          return;
        }
        setTopicsError(err.message);
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const subjectsForGrade = subjects.filter((s) => String(s.grade) === String(grade));
  const topicsForSubject = topics.filter((t) => t.subject_id === subjectId);

  const handleGradeChange = (e) => {
    setGrade(e.target.value);
    setSubjectId("");
    setTopicId("");
  };

  const handleSubjectChange = (e) => {
    setSubjectId(e.target.value);
    setTopicId("");
  };

  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);
  const [createdSummary, setCreatedSummary] = useState(null);

  const toggleLearner = (id) => {
    setSelectedLearnerIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  };

  const handleAddQuestion = async (e) => {
    e.preventDefault();
    if (!topicId || !questionText.trim() || !modelAnswer.trim() || addingQuestion) return;
    setAddingQuestion(true);
    setQuestionError(null);
    try {
      const created = await createCustomQuestion({
        token,
        topicId,
        text: questionText.trim(),
        modelAnswer: modelAnswer.trim(),
      });
      setDraftQuestions((prev) => [...prev, { id: created.id, text: created.text }]);
      setQuestionText("");
      setModelAnswer("");
    } catch (err) {
      if (err.status === 401) {
        onLogout();
        return;
      }
      setQuestionError(err.message);
    } finally {
      setAddingQuestion(false);
    }
  };

  const removeDraftQuestion = (id) => {
    setDraftQuestions((prev) => prev.filter((q) => q.id !== id));
  };

  const handleCreateAssignment = async (e) => {
    e.preventDefault();
    if (!title.trim() || draftQuestions.length === 0 || selectedLearnerIds.length === 0) return;
    if (submitting) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      const created = await createAssignment({
        token,
        title: title.trim(),
        instructions: instructions.trim() || undefined,
        dueAt: dueAt ? new Date(dueAt).toISOString() : undefined,
        questionIds: draftQuestions.map((q) => q.id),
        learnerIds: selectedLearnerIds,
      });
      setCreatedSummary(created);
      setTitle("");
      setInstructions("");
      setDueAt("");
      setDraftQuestions([]);
      setSelectedLearnerIds([]);
      onCreated();
    } catch (err) {
      if (err.status === 401) {
        onLogout();
        return;
      }
      setSubmitError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="admin-form">
      <h3 className="admin-screen__subheading">Create an assignment</h3>

      <label className="admin-form__field">
        <span>Title</span>
        <input type="text" value={title} onChange={(e) => setTitle(e.target.value)} required />
      </label>
      <label className="admin-form__field">
        <span>Instructions (optional)</span>
        <input
          type="text"
          value={instructions}
          onChange={(e) => setInstructions(e.target.value)}
        />
      </label>
      <label className="admin-form__field">
        <span>Due date (optional)</span>
        <input type="date" value={dueAt} onChange={(e) => setDueAt(e.target.value)} />
      </label>

      <fieldset className="admin-form__fieldset">
        <legend>Add a question</legend>
        {subjectsError && <div className="admin-screen__error">{subjectsError}</div>}
        {topicsError && <div className="admin-screen__error">{topicsError}</div>}
        <label className="admin-form__field">
          <span>Grade</span>
          <select value={grade} onChange={handleGradeChange}>
            <option value="">Select a grade…</option>
            <option value={10}>10</option>
            <option value={11}>11</option>
            <option value={12}>12</option>
          </select>
        </label>
        <label className="admin-form__field">
          <span>Subject</span>
          <select value={subjectId} onChange={handleSubjectChange} disabled={!grade}>
            <option value="">
              {grade ? "Select a subject…" : "Select a grade first"}
            </option>
            {subjectsForGrade.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        </label>
        <label className="admin-form__field">
          <span>Topic</span>
          <select value={topicId} onChange={(e) => setTopicId(e.target.value)} disabled={!subjectId}>
            <option value="">
              {subjectId ? "Select a topic…" : "Select a subject first"}
            </option>
            {topicsForSubject.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name}
              </option>
            ))}
          </select>
        </label>
        <label className="admin-form__field">
          <span>Question text</span>
          <textarea value={questionText} onChange={(e) => setQuestionText(e.target.value)} />
        </label>
        <label className="admin-form__field">
          <span>Model answer</span>
          <textarea value={modelAnswer} onChange={(e) => setModelAnswer(e.target.value)} />
        </label>
        {questionError && <div className="admin-screen__error">{questionError}</div>}
        <button
          type="button"
          className="admin-form__primary-button"
          onClick={handleAddQuestion}
          disabled={addingQuestion}
        >
          {addingQuestion ? "Adding…" : "Add question to this assignment"}
        </button>

        {draftQuestions.length > 0 && (
          <ul className="admin-errors">
            {draftQuestions.map((q) => (
              <li key={q.id}>
                {q.text}{" "}
                <button
                  type="button"
                  className="admin-screen__link-button"
                  onClick={() => removeDraftQuestion(q.id)}
                >
                  Remove
                </button>
              </li>
            ))}
          </ul>
        )}
      </fieldset>

      <fieldset className="admin-form__fieldset">
        <legend>Assign to</legend>
        {students.length === 0 && (
          <p className="admin-screen__muted">No students yet — add one on the Students tab first.</p>
        )}
        {students.map((s) => (
          <label key={s.learner_id} className="admin-form__checkbox-row">
            <input
              type="checkbox"
              checked={selectedLearnerIds.includes(s.learner_id)}
              onChange={() => toggleLearner(s.learner_id)}
            />
            {s.display_name} (Grade {s.grade})
          </label>
        ))}
      </fieldset>

      {submitError && <div className="admin-screen__error">{submitError}</div>}
      <button
        type="button"
        className="admin-form__primary-button"
        onClick={handleCreateAssignment}
        disabled={
          submitting || !title.trim() || draftQuestions.length === 0 || selectedLearnerIds.length === 0
        }
      >
        {submitting ? "Creating…" : "Create assignment"}
      </button>

      {createdSummary && (
        <p className="admin-screen__muted">
          “{createdSummary.title}” created with {createdSummary.question_count} question(s) for{" "}
          {createdSummary.target_count} student(s).
        </p>
      )}
    </div>
  );
}
