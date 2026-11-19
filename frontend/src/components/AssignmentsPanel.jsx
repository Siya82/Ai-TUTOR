/*
 * Moved 20 Nov 2026 out of TeacherAdminScreen.jsx (deep scan L4) -- no
 * behaviour change. TEACH's Assignments tab: the list of a teacher's
 * assignments, their results, and the form that creates one (ADR-028).
 */
import { useEffect, useState } from "react";
import AnswerReview from "./AnswerReview";
import AssignmentControls from "./AssignmentControls";
import {
  createAssignment,
  createCustomQuestion,
  fetchBankQuestions,
  fetchClasses,
  fetchSubjects,
  fetchTeachAssignment,
  fetchTeachAssignments,
  fetchTopics,
  releaseAssignmentResults,
} from "../api";
export default function AssignmentsPanel({ token, onLogout, students, me }) {
  const [assignments, setAssignments] = useState([]);
  const [listLoading, setListLoading] = useState(true);
  const [listError, setListError] = useState(null);
  const [selected, setSelected] = useState(null);
  const [detail, setDetail] = useState(null);
  const [detailError, setDetailError] = useState(null);
  const [releasing, setReleasing] = useState(false);
  const [reviewing, setReviewing] = useState(null); // code review 19 Nov #2: learner_id

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
    // Code review #17: run the fetch just after the effect (not in its
    // synchronous body) so the loading/error resets don't cascade renders.
    const id = setTimeout(loadAssignments, 0);
    return () => clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const openDetail = async (id, keep = false) => {
    setSelected(id);
    if (!keep) {
      setDetail(null);
      setReviewing(null);
    }
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

  // NEW (ADR-029). Only meaningful for a "test"-mode assignment that
  // hasn't been released yet -- the button itself is only rendered in
  // that state below. Reloads both the open detail and the list (so
  // the released badge updates in the table too) rather than trying
  // to patch either in place.
  const handleRelease = async () => {
    if (!selected || releasing) return;
    setReleasing(true);
    try {
      await releaseAssignmentResults(token, selected);
      await openDetail(selected);
      await loadAssignments();
    } catch (err) {
      if (err.status === 401) {
        onLogout();
        return;
      }
      setDetailError(err.message);
    } finally {
      setReleasing(false);
    }
  };

  return (
    <div className="admin-panel">
      <CreateAssignmentForm
        token={token}
        onLogout={onLogout}
        students={students}
        me={me}
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
              <th>Mode</th>
              <th>Due</th>
              <th>Questions</th>
              <th>Marks</th>
              <th>Students</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {assignments.map((a) => (
              <tr key={a.id}>
                <td>
                  {a.title}
                  {/* Code review #12: oversight view shows who set it */}
                  {!a.is_mine && a.teacher_name && (
                    <div className="admin-screen__muted">set by {a.teacher_name}</div>
                  )}
                </td>
                <td>
                  {a.mode === "test"
                    ? a.results_released
                      ? "Test (released)"
                      : "Test (withheld)"
                    : "Practice"}
                </td>
                <td>{a.due_at ? new Date(a.due_at).toLocaleDateString() : "—"}</td>
                <td>{a.question_count}</td>
                <td>{a.marks_total}</td>
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
              <p className="admin-result__title">
                {detail.title} — completion
                {detail.mode === "test" && (
                  <span className="admin-screen__muted">
                    {" "}
                    ({detail.results_released ? "results released" : "results withheld from students"})
                  </span>
                )}
              </p>
              {detail.mode === "test" &&
                !detail.results_released &&
                assignments.find((a) => a.id === selected)?.can_release !== false && (
                <button type="button" onClick={handleRelease} disabled={releasing}>
                  {releasing ? "Releasing…" : "Release results to students"}
                </button>
              )}
              {detail.can_change && (
                <AssignmentControls
                  key={detail.id}
                  token={token}
                  detail={detail}
                  onChanged={async () => {
                    await openDetail(detail.id, true);
                    await loadAssignments();
                  }}
                  onDeleted={async () => {
                    setSelected(null);
                    setDetail(null);
                    await loadAssignments();
                  }}
                  onDuplicated={async (id) => {
                    await loadAssignments();
                    await openDetail(id);
                  }}
                />
              )}
              <table className="admin-table">
                <thead>
                  <tr>
                    <th>Student</th>
                    <th>Status</th>
                    <th>Answered</th>
                    <th>Correct</th>
                    <th>Marks</th>
                    <th />
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
                      <td>
                        {c.marks_earned} / {c.marks_total}
                      </td>
                      <td>
                        {c.answered_count > 0 && (
                          <button
                            type="button"
                            className="admin-screen__link-button"
                            onClick={() => setReviewing(c.learner_id)}
                          >
                            View answers
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {reviewing && (
                <AnswerReview
                  key={reviewing}
                  token={token}
                  assignmentId={detail.id}
                  learnerId={reviewing}
                  onClose={() => setReviewing(null)}
                  onChanged={() => openDetail(detail.id, true)}
                />
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}

function CreateAssignmentForm({ token, onLogout, students, me, onCreated }) {
  const [title, setTitle] = useState("");
  const [instructions, setInstructions] = useState("");
  const [dueAt, setDueAt] = useState("");
  const [selectedLearnerIds, setSelectedLearnerIds] = useState([]);
  // NEW 17 Nov 2026 (ADR-031): whole classes can be targeted too
  const [classes, setClasses] = useState([]);
  const [selectedClassIds, setSelectedClassIds] = useState([]);

  // NEW (ADR-029): "practice" (default) shows AI feedback the instant
  // a student answers, exactly as every assignment behaved before this
  // -- "test" withholds it until the teacher clicks "Release results"
  // on AssignmentsPanel's detail view above.
  const [mode, setMode] = useState("practice");

  // The list of questions attached to this not-yet-submitted
  // assignment -- each either freshly authored below, or added from
  // the reusable bank list (NEW, ADR-029: "derive some questions from
  // the textbook and some create on their own"). Each carries its own
  // marks value (default 1, editable) -- a question's point value is
  // a fact about how it's used in THIS assignment, not the question.
  // [{id, text, marks}]
  const [draftQuestions, setDraftQuestions] = useState([]);

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

  const [subjects, setSubjects] = useState([]);
  const [subjectsError, setSubjectsError] = useState(null);
  const [topics, setTopics] = useState([]);
  const [topicsError, setTopicsError] = useState(null);

  // NEW (ADR-029): the reusable question bank for whichever topic is
  // currently selected -- every seeded CAPS question for it plus this
  // teacher's own previously-authored custom ones. Reloaded whenever
  // topicId changes; empty/cleared while no topic is selected yet.
  const [bankQuestions, setBankQuestions] = useState([]);
  const [bankLoading, setBankLoading] = useState(false);
  const [bankError, setBankError] = useState(null);

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
    fetchClasses(token)
      .then(setClasses)
      .catch(() => setClasses([]));
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

  // Same "fetch on a dependency change" shape as loadRoster()/
  // loadAssignments() above and AssignmentsView.jsx's own load()
  // effect -- this file and that one already carry this exact
  // pre-existing react-hooks/set-state-in-effect pattern unresolved,
  // so the disables below aren't a new category of lint debt, just
  // one more instance of it.
  useEffect(() => {
    // Code review #17: run the fetch just after the effect (not in its
    // synchronous body) so the loading/error resets don't cascade renders.
    let cancelled = false;
    const id = setTimeout(() => {
      setBankError(null);
      if (!topicId) {
        setBankQuestions([]);
        return;
      }
      setBankLoading(true);
      fetchBankQuestions(token, topicId)
        .then((qs) => {
          if (!cancelled) setBankQuestions(qs);
        })
        .catch((err) => {
          if (cancelled) return;
          if (err.status === 401) {
            onLogout();
            return;
          }
          setBankError(err.message);
        })
        .finally(() => {
          if (!cancelled) setBankLoading(false);
        });
    }, 0);
    return () => {
      cancelled = true;
      clearTimeout(id);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [topicId]);

  // NEW 17 Nov 2026 (ADR-031): only subjects this teacher may assign in
  // (their allocations / department), unless they're whole-school staff.
  // The server rejects anything else anyway; this just avoids offering it.
  const allowedSubjectIds = me && !me.whole_school_academic ? new Set(me.visible_subject_ids) : null;
  const allowedSubjects = allowedSubjectIds
    ? subjects.filter((s) => allowedSubjectIds.has(s.id))
    : subjects;
  const gradeOptions = [...new Set(allowedSubjects.map((s) => s.grade))].sort((a, b) => a - b);
  const subjectsForGrade = allowedSubjects.filter((s) => String(s.grade) === String(grade));
  const topicsForSubject = topics.filter((t) => t.subject_id === subjectId);
  const draftQuestionIds = new Set(draftQuestions.map((q) => q.id));

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

  const hasTargets = selectedLearnerIds.length > 0 || selectedClassIds.length > 0;

  // UPDATED 17 Nov 2026 (Siya: "the drop down should show the classes the
  // teacher is assigned to"). A class is offered when the teacher teaches
  // it -- a class allocation, or a whole-grade allocation covering it --
  // and, once questions are added, only for the subject(s) of those
  // questions. Principals/deputies/school admins see every class. The
  // server re-checks all of this when the assignment is created.
  const topicSubjectId = (tid) => topics.find((t) => t.id === tid)?.subject_id || null;
  const draftSubjectIds = new Set(draftQuestions.map((q) => q.subjectId).filter(Boolean));
  const seesAllClasses = Boolean(me?.can_manage_school || me?.whole_school_academic);
  const subjectGrade = (sid) => subjects.find((sub) => sub.id === sid)?.grade;
  const myClassOptions = classes
    .map((c) => {
      const mine = c.allocations.filter((a) => a.teacher_user_id === me?.user_id);
      const teaches = [...new Set(mine.map((a) => a.subject_name))];
      return { ...c, mine, teaches };
    })
    .filter((c) => seesAllClasses || c.mine.length > 0)
    .filter((c) => {
      if (draftSubjectIds.size === 0) return true;
      if (seesAllClasses && c.mine.length === 0) {
        return [...draftSubjectIds].every((sid) => subjectGrade(sid) === c.grade);
      }
      return [...draftSubjectIds].every((sid) => c.mine.some((a) => a.subject_id === sid));
    });
  const classOptionsToAdd = myClassOptions.filter((c) => !selectedClassIds.includes(c.id));
  const selectedClasses = classes.filter((c) => selectedClassIds.includes(c.id));
  const [targetMode, setTargetMode] = useState("class"); // "class" | "learners"
  const addClass = (id) => {
    if (id) setSelectedClassIds((prev) => (prev.includes(id) ? prev : [...prev, id]));
  };
  const removeClass = (id) => setSelectedClassIds((prev) => prev.filter((x) => x !== id));

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
      setDraftQuestions((prev) => [
        ...prev,
        { id: created.id, text: created.text, marks: 1, subjectId: topicSubjectId(created.topic_id) },
      ]);
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

  // NEW (ADR-029): adds a question straight from the bank list below
  // instead of authoring a new one -- same draftQuestions shape, just
  // skipping the create_custom_question() round-trip since the
  // question already exists.
  const addBankQuestion = (q) => {
    if (draftQuestionIds.has(q.id)) return;
    setDraftQuestions((prev) => [
      ...prev,
      { id: q.id, text: q.text, marks: 1, subjectId: topicSubjectId(q.topic_id) },
    ]);
  };

  const removeDraftQuestion = (id) => {
    setDraftQuestions((prev) => prev.filter((q) => q.id !== id));
  };

  const setDraftQuestionMarks = (id, marks) => {
    const parsed = Math.max(1, Math.min(100, Number(marks) || 1));
    setDraftQuestions((prev) => prev.map((q) => (q.id === id ? { ...q, marks: parsed } : q)));
  };

  const handleCreateAssignment = async (e) => {
    e.preventDefault();
    if (!title.trim() || draftQuestions.length === 0 || !hasTargets) return;
    if (submitting) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      const created = await createAssignment({
        token,
        title: title.trim(),
        instructions: instructions.trim() || undefined,
        dueAt: dueAt ? new Date(dueAt).toISOString() : undefined,
        mode,
        questions: draftQuestions,
        learnerIds: selectedLearnerIds,
        classIds: selectedClassIds,
      });
      setCreatedSummary(created);
      setTitle("");
      setInstructions("");
      setDueAt("");
      setMode("practice");
      setDraftQuestions([]);
      setSelectedLearnerIds([]);
      setSelectedClassIds([]);
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
      <label className="admin-form__field">
        <span>Mode</span>
        <select value={mode} onChange={(e) => setMode(e.target.value)}>
          <option value="practice">Practice — AI feedback shows right away</option>
          <option value="test">Test — results withheld until you release them</option>
        </select>
      </label>

      <fieldset className="admin-form__fieldset">
        <legend>Add a question</legend>
        {subjectsError && <div className="admin-screen__error">{subjectsError}</div>}
        {topicsError && <div className="admin-screen__error">{topicsError}</div>}
        <label className="admin-form__field">
          <span>Grade</span>
          <select value={grade} onChange={handleGradeChange}>
            <option value="">Select a grade…</option>
            {gradeOptions.map((g) => (
              <option key={g} value={g}>
                {g}
              </option>
            ))}
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

        {topicId && (
          <div className="admin-form__field">
            <span>Reuse an existing question for this topic</span>
            {bankLoading && <p className="admin-screen__muted">Loading question bank…</p>}
            {bankError && <div className="admin-screen__error">{bankError}</div>}
            {!bankLoading && !bankError && bankQuestions.length === 0 && (
              <p className="admin-screen__muted">
                No existing questions for this topic yet — write a new one below.
              </p>
            )}
            {!bankLoading && !bankError && bankQuestions.length > 0 && (
              <ul className="admin-errors">
                {bankQuestions.map((q) => (
                  <li key={q.id}>
                    {q.text}{" "}
                    <button
                      type="button"
                      className="admin-screen__link-button"
                      onClick={() => addBankQuestion(q)}
                      disabled={draftQuestionIds.has(q.id)}
                    >
                      {draftQuestionIds.has(q.id) ? "Added" : "Add"}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        <label className="admin-form__field">
          <span>Or write a new question</span>
          <textarea
            value={questionText}
            onChange={(e) => setQuestionText(e.target.value)}
            placeholder="Question text"
          />
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
                <label>
                  Marks:{" "}
                  <input
                    type="number"
                    min={1}
                    max={100}
                    value={q.marks}
                    onChange={(e) => setDraftQuestionMarks(q.id, e.target.value)}
                    className="admin-form__marks-input"
                  />
                </label>{" "}
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
        <div className="progress-filter" role="radiogroup" aria-label="Who gets this assignment">
          {[
            ["class", "A whole class"],
            ["learners", "Individual learners"],
          ].map(([id, label]) => (
            <button
              key={id}
              type="button"
              role="radio"
              aria-checked={targetMode === id}
              className={`progress-filter__chip${targetMode === id ? " progress-filter__chip--active" : ""}`}
              onClick={() => setTargetMode(id)}
            >
              {label}
            </button>
          ))}
        </div>

        {targetMode === "class" && (
          <>
            {myClassOptions.length === 0 && selectedClasses.length === 0 ? (
              <p className="admin-screen__muted">
                {classes.length === 0
                  ? "You aren't allocated to any classes yet. Ask your principal or school admin to allocate you a class, or pick individual learners instead."
                  : "None of your classes are taught the subject of the questions you've added. Pick individual learners instead, or change the questions."}
              </p>
            ) : (
              <label className="admin-form__field">
                <span>Class</span>
                <select value="" onChange={(e) => addClass(e.target.value)}>
                  <option value="">
                    {classOptionsToAdd.length ? "Choose one of your classes…" : "All your classes are added"}
                  </option>
                  {classOptionsToAdd.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name} · Grade {c.grade}
                      {c.teaches.length ? ` · ${c.teaches.join(", ")}` : ""} · {c.member_count} learner
                      {c.member_count === 1 ? "" : "s"}
                    </option>
                  ))}
                </select>
              </label>
            )}
            {draftSubjectIds.size > 0 && myClassOptions.length > 0 && (
              <p className="admin-screen__muted">Showing only classes you teach this subject to.</p>
            )}
            {selectedClasses.length > 0 && (
              <div className="staff-card__chips">
                {selectedClasses.map((c) => (
                  <span key={c.id} className="chip">
                    {c.name} ({c.member_count} learner{c.member_count === 1 ? "" : "s"})
                    <button
                      type="button"
                      className="chip__remove"
                      aria-label={`Remove ${c.name}`}
                      onClick={() => removeClass(c.id)}
                    >
                      ×
                    </button>
                  </span>
                ))}
              </div>
            )}
          </>
        )}

        {targetMode === "learners" && (
          <>
            {students.length === 0 && <p className="admin-screen__muted">No learners available to you yet.</p>}
            {students
              .filter((st) => st.is_active !== false)
              .map((st) => (
                <label key={st.learner_id} className="admin-form__checkbox-row">
                  <input
                    type="checkbox"
                    checked={selectedLearnerIds.includes(st.learner_id)}
                    onChange={() => toggleLearner(st.learner_id)}
                  />
                  {st.display_name} (Grade {st.grade})
                </label>
              ))}
          </>
        )}

        {hasTargets && (
          <p className="admin-screen__muted">
            Going to {selectedClassIds.length > 0 && `${selectedClassIds.length} class${selectedClassIds.length === 1 ? "" : "es"}`}
            {selectedClassIds.length > 0 && selectedLearnerIds.length > 0 && " and "}
            {selectedLearnerIds.length > 0 &&
              `${selectedLearnerIds.length} individual learner${selectedLearnerIds.length === 1 ? "" : "s"}`}
            . Learners who join a class later won't get it automatically.
          </p>
        )}
      </fieldset>

      {submitError && <div className="admin-screen__error">{submitError}</div>}
      <button
        type="button"
        className="admin-form__primary-button"
        onClick={handleCreateAssignment}
        disabled={
          submitting || !title.trim() || draftQuestions.length === 0 || !hasTargets
        }
      >
        {submitting ? "Creating…" : "Create assignment"}
      </button>

      {createdSummary && (
        <p className="admin-screen__muted">
          “{createdSummary.title}” created with {createdSummary.question_count} question(s) worth{" "}
          {createdSummary.marks_total} mark(s) total, for {createdSummary.target_count} student(s).
        </p>
      )}
    </div>
  );
}
