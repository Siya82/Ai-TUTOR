/*
 * NEW 19 Nov 2026 (code review 19 Nov #2). What one learner actually wrote
 * for each question, the AI's mark and feedback, and the teacher's power to
 * correct the mark (with a note the learner sees once results are visible).
 */
import { useEffect, useState } from "react";
import { Check, X } from "lucide-react";
import { fetchLearnerAnswers, overrideMark } from "../api";
import { ICON_BUTTON } from "./icons";
import { MathText } from "./MathText";

function QuestionReview({ token, assignmentId, q, canMark, onChanged }) {
  const [note, setNote] = useState(q.teacher_note || "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const mark = async (isCorrect) => {
    setBusy(true);
    setError(null);
    try {
      await overrideMark(token, assignmentId, q.attempt_id, isCorrect, note.trim());
      await onChanged();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <li className="answer-review__item">
      <div className="answer-review__question">
        <MathText text={q.text} /> <span className="admin-screen__muted">[{q.marks}]</span>
      </div>
      {q.attempt_id ? (
        <>
          <div className="answer-review__answer">
            <span className="admin-screen__muted">Answer{q.tries > 1 ? ` (try ${q.tries})` : ""}:</span>{" "}
            <MathText text={q.learner_response} />
          </div>
          <div className="admin-screen__muted">
            Model answer: <MathText text={q.model_answer} />
          </div>
          <div
            className={`answer-review__mark answer-review__mark--${
              q.is_correct === true ? "right" : q.is_correct === false ? "wrong" : "none"
            }`}
          >
            {q.is_correct === true ? "Correct" : q.is_correct === false ? "Not correct" : "Not marked"}
            {" · "}
            {q.marked_by_teacher ? "marked by a teacher" : "marked by THUTOra"}
          </div>
          {q.ai_feedback && <p className="answer-review__feedback">{q.ai_feedback}</p>}
          {canMark && (
            <div className="answer-review__actions">
              <input
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder="Note to the learner (optional)"
                maxLength={1000}
              />
              <button type="button" className="answer-review__btn" onClick={() => mark(true)} disabled={busy}>
                <Check size={ICON_BUTTON} aria-hidden="true" /> Mark right
              </button>
              <button type="button" className="answer-review__btn" onClick={() => mark(false)} disabled={busy}>
                <X size={ICON_BUTTON} aria-hidden="true" /> Mark wrong
              </button>
            </div>
          )}
          {error && <div className="admin-screen__error">{error}</div>}
        </>
      ) : (
        <p className="admin-screen__muted">Not answered yet.</p>
      )}
    </li>
  );
}

export default function AnswerReview({ token, assignmentId, learnerId, onClose, onChanged }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  const load = () =>
    fetchLearnerAnswers(token, assignmentId, learnerId)
      .then(setData)
      .catch((err) => setError(err.message));

  useEffect(() => {
    const id = setTimeout(load, 0);
    return () => clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [assignmentId, learnerId]);

  return (
    <div className="admin-result answer-review">
      <div className="privacy-notice__header">
        <p className="admin-result__title">Answers — {data?.display_name || "…"}</p>
        <button type="button" className="admin-screen__link-button" onClick={onClose}>
          Close
        </button>
      </div>
      {error && <div className="admin-screen__error">{error}</div>}
      {data && (
        <ol className="answer-review__list">
          {data.questions.map((q) => (
            <QuestionReview
              key={q.question_id}
              token={token}
              assignmentId={assignmentId}
              q={q}
              canMark={data.can_mark}
              onChanged={async () => {
                await load();
                await onChanged?.();
              }}
            />
          ))}
        </ol>
      )}
    </div>
  );
}
