/*
 * NEW 15 Nov 2026 (ADR-028, assignments). The student-facing half of
 * the Assignments feature -- what a teacher issues via
 * TeacherAdminScreen.jsx's "Assignments" tab shows up here. Rendered
 * by ChatScreen.jsx as an alternate view (a lightweight in-screen
 * toggle, not a separate route) alongside the existing tutor chat.
 *
 * Deliberately simple: a list of assigned work with computed status,
 * and one assignment's questions with a plain textarea per question --
 * no rich editor, no attachments (unlike the tutor chat's composer),
 * since ADR-028 scoped assignments to text answers only for this pass.
 */

import { useEffect, useState } from "react";
import { fetchMyAssignment, fetchMyAssignments, submitAssignmentAnswer } from "../api";

function statusLabel(status) {
  return { not_started: "Not started", in_progress: "In progress", completed: "Completed" }[status] || status;
}

export default function AssignmentsView({ auth, onLogout }) {
  const [assignments, setAssignments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [openId, setOpenId] = useState(null);

  const loadAssignments = async () => {
    setLoading(true);
    setError(null);
    try {
      const list = await fetchMyAssignments(auth.token);
      setAssignments(list);
    } catch (err) {
      if (err.status === 401) {
        onLogout();
        return;
      }
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // Code review #17: run the fetch just after the effect (not in its
    // synchronous body) so the loading/error resets don't cascade renders.
    const id = setTimeout(loadAssignments, 0);
    return () => clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (openId) {
    return (
      <AssignmentDetail
        auth={auth}
        onLogout={onLogout}
        assignmentId={openId}
        onBack={() => {
          setOpenId(null);
          loadAssignments(); // pick up any status change from answers just submitted
        }}
      />
    );
  }

  return (
    <div className="assignments-view">
      <h2 className="assignments-view__heading">My assignments</h2>
      {loading && <p className="admin-screen__muted">Loading assignments…</p>}
      {error && (
        <div className="admin-screen__error">
          {error}{" "}
          <button type="button" className="admin-screen__link-button" onClick={loadAssignments}>
            Try again
          </button>
        </div>
      )}
      {!loading && !error && assignments.length === 0 && (
        <p className="admin-screen__muted">No assignments yet — your teacher hasn't issued any.</p>
      )}
      {!loading && !error && assignments.length > 0 && (
        <ul className="assignments-list">
          {assignments.map((a) => (
            <li key={a.id} className="assignments-list__item">
              <button type="button" className="assignments-list__button" onClick={() => setOpenId(a.id)}>
                <span className="assignments-list__title">{a.title}</span>
                <span className={`assignments-list__status assignments-list__status--${a.status}`}>
                  {statusLabel(a.status)}
                </span>
              </button>
              {a.instructions && <p className="assignments-list__instructions">{a.instructions}</p>}
              <p className="admin-screen__muted">
                {a.answered_count} / {a.question_count} answered
                {a.due_at ? ` — due ${new Date(a.due_at).toLocaleDateString()}` : ""}
                {a.mode === "test"
                  ? a.marks_earned === null
                    ? " — results withheld until your teacher releases them"
                    : ` — ${a.marks_earned} / ${a.marks_total} marks`
                  : a.answered_count > 0
                    ? ` — ${a.marks_earned} / ${a.marks_total} marks`
                    : ""}
              </p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function AssignmentDetail({ auth, onLogout, assignmentId, onBack }) {
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const d = await fetchMyAssignment(auth.token, assignmentId);
      setDetail(d);
    } catch (err) {
      if (err.status === 401) {
        onLogout();
        return;
      }
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // Code review #17: run the fetch just after the effect (not in its
    // synchronous body) so the loading/error resets don't cascade renders.
    const id = setTimeout(load, 0);
    return () => clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [assignmentId]);

  const handleAnswered = (questionId, result) => {
    // Merges the just-returned mark/feedback straight into local state
    // rather than refetching the whole assignment -- the question list
    // order and text don't change, only this one question's answered/
    // is_correct/ai_feedback/feedback_withheld fields do. feedback_withheld
    // (ADR-029) is true for a "test"-mode assignment whose results
    // haven't been released yet -- is_correct/ai_feedback are already
    // null in that case (the backend withholds them), never shown.
    setDetail((prev) => ({
      ...prev,
      questions: prev.questions.map((q) =>
        q.id === questionId
          ? {
              ...q,
              answered: true,
              is_correct: result.is_correct,
              ai_feedback: result.feedback,
              feedback_withheld: result.feedback_withheld,
            }
          : q
      ),
    }));
  };

  return (
    <div className="assignments-view">
      <button type="button" className="admin-screen__link-button" onClick={onBack}>
        ← Back to assignments
      </button>
      {loading && <p className="admin-screen__muted">Loading…</p>}
      {error && <div className="admin-screen__error">{error}</div>}
      {detail && (
        <>
          <h2 className="assignments-view__heading">{detail.title}</h2>
          {detail.instructions && <p className="assignments-list__instructions">{detail.instructions}</p>}
          {detail.due_at && (
            <p className="admin-screen__muted">Due {new Date(detail.due_at).toLocaleDateString()}</p>
          )}
          {detail.mode === "test" && (
            <p className="admin-screen__muted">
              {detail.results_released
                ? "This is a test — results have been released."
                : "This is a test — your answers are recorded, but results and feedback are withheld until your teacher releases them."}
            </p>
          )}
          {detail.answers_closed && (
            // NEW 17 Nov 2026 (code review #2): a released or overdue test
            <div className="admin-screen__muted assignments-view__closed">{detail.answers_closed}</div>
          )}
          <ol className="assignment-questions">
            {detail.questions.map((q) => (
              <AssignmentQuestionCard
                key={q.id}
                auth={auth}
                onLogout={onLogout}
                assignmentId={assignmentId}
                question={q}
                closed={Boolean(detail.answers_closed)}
                onAnswered={(result) => handleAnswered(q.id, result)}
              />
            ))}
          </ol>
        </>
      )}
    </div>
  );
}

function AssignmentQuestionCard({ auth, onLogout, assignmentId, question, closed, onAnswered }) {
  // Pre-fills from the student's own prior answer (question.learner_response)
  // so reopening an already-answered question shows what they wrote,
  // rather than an empty box -- this textarea is otherwise a plain,
  // uncontrolled-feeling draft, same posture as ChatScreen's composer.
  const [response, setResponse] = useState(question.learner_response || "");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!response.trim() || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      const result = await submitAssignmentAnswer({
        token: auth.token,
        assignmentId,
        questionId: question.id,
        learnerResponse: response.trim(),
      });
      onAnswered(result);
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
    <li className="assignment-question-card">
      <p className="assignment-question-card__text">
        {question.text} <span className="admin-screen__muted">({question.marks} mark{question.marks === 1 ? "" : "s"})</span>
      </p>
      {closed ? (
        question.learner_response && (
          <p className="assignment-question-card__answer">
            <span className="admin-screen__muted">Your answer: </span>
            {question.learner_response}
          </p>
        )
      ) : (
      <form onSubmit={handleSubmit}>
        <textarea
          className="assignment-question-card__textarea"
          value={response}
          onChange={(e) => setResponse(e.target.value)}
          placeholder="Type your answer…"
          maxLength={4000}
        />
        {error && <div className="admin-screen__error">{error}</div>}
        <button type="submit" disabled={submitting || !response.trim()}>
          {submitting ? "Submitting…" : question.answered ? "Re-submit answer" : "Submit answer"}
        </button>
      </form>
      )}

      {question.answered && question.feedback_withheld && (
        // NEW (ADR-029): a "test"-mode assignment whose results haven't
        // been released yet -- no hint of correctness at all, not even
        // "unmarked" (which, before this, was indistinguishable from an
        // actual marking failure). The real mark is already recorded
        // server-side; this is purely about what's shown here.
        <div className="assignment-question-card__result assignment-question-card__result--withheld">
          <strong>Submitted</strong>
          <p>Your answer has been recorded. Your teacher will release the result.</p>
        </div>
      )}

      {question.answered && !question.feedback_withheld && (
        <div
          className={
            "assignment-question-card__result" +
            (question.is_correct === true
              ? " assignment-question-card__result--correct"
              : question.is_correct === false
                ? " assignment-question-card__result--incorrect"
                : " assignment-question-card__result--unmarked")
          }
        >
          <strong>
            {question.is_correct === true
              ? "Correct"
              : question.is_correct === false
                ? "Not quite"
                : "Unmarked"}
          </strong>
          {question.ai_feedback && <p>{question.ai_feedback}</p>}
        </div>
      )}
    </li>
  );
}
