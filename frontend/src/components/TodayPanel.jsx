/*
 * NEW 19 Nov 2026 (ADR-036): the teacher's "Today" tab -- the first thing a
 * teacher sees. From their own learners' answers over the last week:
 * who needs help, which topics are weakest (with a one-click practice set
 * for the learners who struggled), who hasn't practised, and their own
 * assignments due soon.
 */
import { useEffect, useState } from "react";
import { CalendarClock, HandHelping, Moon, Sparkles, TrendingDown } from "lucide-react";
import { createTodayPractice, fetchToday } from "../api";
import { ICON_BUTTON, ICON_INLINE } from "./icons";

function Card({ icon: Icon, title, children }) {
  return (
    <section className="today-card">
      <h3 className="today-card__title">
        <span className="icon-chip">
          <Icon size={ICON_BUTTON} aria-hidden="true" />
        </span>
        {title}
      </h3>
      {children}
    </section>
  );
}

export default function TodayPanel({ token, onGoToAssignments }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [busyTopic, setBusyTopic] = useState(null);
  const [made, setMade] = useState({}); // topic_id -> result
  const [actionError, setActionError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    const id = setTimeout(() => {
      fetchToday(token)
        .then((d) => {
          if (!cancelled) setData(d);
        })
        .catch((err) => {
          if (!cancelled) setError(err.message);
        });
    }, 0);
    return () => {
      cancelled = true;
      clearTimeout(id);
    };
  }, [token]);

  const makePractice = async (topic) => {
    setBusyTopic(topic.topic_id);
    setActionError(null);
    try {
      const result = await createTodayPractice(token, topic.topic_id, topic.learner_ids);
      setMade((m) => ({ ...m, [topic.topic_id]: result }));
    } catch (err) {
      setActionError(err.message);
    } finally {
      setBusyTopic(null);
    }
  };

  if (error) return <div className="admin-screen__error">{error}</div>;
  if (!data) return <p className="admin-screen__muted">Loading today's overview…</p>;

  const nothingYet = data.active_count === 0;
  return (
    <div className="today">
      <p className="today__lede">
        {data.learner_count === 0
          ? "You don't have any learners yet. Once your principal allocates you a class, this page shows who needs help each day."
          : `In the last ${data.window_days} days, ${data.active_count} of your ${data.learner_count} learners answered questions.`}
      </p>
      {actionError && <div className="admin-screen__error">{actionError}</div>}

      <div className="today__grid">
        <Card icon={HandHelping} title="Needs help">
          {data.needs_help.length === 0 ? (
            <p className="admin-screen__muted">
              {nothingYet ? "Nothing to show until learners answer some questions." : "Nobody is repeatedly stuck."}
            </p>
          ) : (
            <ul className="today-list">
              {data.needs_help.slice(0, 8).map((h) => (
                <li key={`${h.learner_id}-${h.topic_id}`}>
                  <strong>{h.learner_name}</strong> — {h.topic_name}
                  <span className="admin-screen__muted">
                    {" "}
                    · {h.wrong} of {h.answered} wrong
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card icon={TrendingDown} title="Weakest topics">
          {data.weak_topics.length === 0 ? (
            <p className="admin-screen__muted">No wrong answers this week.</p>
          ) : (
            <ul className="today-list">
              {data.weak_topics.map((w) => (
                <li key={w.topic_id} className="today-list__row">
                  <div>
                    <strong>{w.topic_name}</strong>
                    <div className="admin-screen__muted">
                      Grade {w.grade} {w.subject_name} · {w.accuracy}% right · {w.learner_ids.length} learner
                      {w.learner_ids.length === 1 ? "" : "s"} struggled
                    </div>
                  </div>
                  {made[w.topic_id] ? (
                    <span className="today-list__done">
                      Practice set sent to {made[w.topic_id].learner_count}
                    </span>
                  ) : (
                    <button
                      type="button"
                      className="today-list__action"
                      disabled={busyTopic === w.topic_id}
                      onClick={() => makePractice(w)}
                    >
                      <Sparkles size={ICON_INLINE} aria-hidden="true" />
                      {busyTopic === w.topic_id ? "Creating…" : "Send practice"}
                    </button>
                  )}
                </li>
              ))}
            </ul>
          )}
          {Object.keys(made).length > 0 && (
            <button type="button" className="admin-screen__link-button" onClick={onGoToAssignments}>
              See it under Assignments
            </button>
          )}
        </Card>

        <Card icon={CalendarClock} title="Due soon">
          {data.due_soon.length === 0 ? (
            <p className="admin-screen__muted">None of your assignments are due in the next 3 days.</p>
          ) : (
            <ul className="today-list">
              {data.due_soon.map((d) => (
                <li key={d.assignment_id}>
                  <strong>{d.title}</strong>
                  <span className="admin-screen__muted">
                    {" "}
                    · due {new Date(d.due_at).toLocaleDateString()} · {d.not_finished} of {d.learners} not finished
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card icon={Moon} title="Haven't practised this week">
          {data.quiet_learners.length === 0 ? (
            <p className="admin-screen__muted">Everyone has practised.</p>
          ) : (
            <p className="today__names">
              {data.quiet_learners
                .slice(0, 20)
                .map((q) => q.learner_name)
                .join(", ")}
              {data.quiet_learners.length > 20 && ` and ${data.quiet_learners.length - 20} more`}
            </p>
          )}
        </Card>
      </div>
    </div>
  );
}
