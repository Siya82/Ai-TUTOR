/*
 * NEW 19 Nov 2026 (code review 19 Nov #6). The learner's own progress --
 * the same picture their teacher and parent see: this week, strongest
 * topics, topics to practise (each one click from the tutor), school work.
 * Unreleased test answers aren't counted (the server leaves them out).
 */
import { useEffect, useState } from "react";
import { ClipboardList, Target, TrendingUp } from "lucide-react";
import { fetchMyProgress } from "../api";
import { ICON_BUTTON } from "./icons";

function workStatus(w) {
  if (w.status === "completed") {
    return w.marks_earned == null ? "Done — marks not released yet" : `Done — ${w.marks_earned}/${w.marks_total}`;
  }
  return w.status === "in_progress" ? "Started" : "Not started";
}

export default function MyProgress({ token, topics, onPractise }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    fetchMyProgress(token)
      .then((d) => !cancelled && setData(d))
      .catch((err) => !cancelled && setError(err.message));
    return () => {
      cancelled = true;
    };
  }, [token]);

  if (error) return <div className="chat-screen__error">{error}</div>;
  if (!data) return <p className="admin-screen__muted my-progress">Loading…</p>;

  const topicByName = (name) => topics.find((t) => t.name === name);
  const week = data.week;
  return (
    <div className="my-progress">
      <h2 className="my-progress__title">My progress</h2>
      <div className="stat-row">
        <div className="stat-tile">
          <span className="stat-tile__label">Questions this week</span>
          <span className="stat-tile__value">{week.answered}</span>
        </div>
        <div className="stat-tile">
          <span className="stat-tile__label">Right this week</span>
          <span className="stat-tile__value">{week.accuracy == null ? "—" : `${week.accuracy}%`}</span>
        </div>
        <div className="stat-tile">
          <span className="stat-tile__label">Days you practised</span>
          <span className="stat-tile__value">{week.active_days}</span>
          <span className="stat-tile__sub">out of the last 7</span>
        </div>
      </div>
      <div className="today__grid">
        <section className="today-card">
          <h3 className="today-card__title">
            <span className="icon-chip">
              <Target size={ICON_BUTTON} aria-hidden="true" />
            </span>
            Practise these next
          </h3>
          {data.weakest_topics.length === 0 ? (
            <p className="admin-screen__muted">Nothing flagged yet — keep answering questions and this fills in.</p>
          ) : (
            <ul className="today-list">
              {data.weakest_topics.map((t) => {
                const topic = topicByName(t.topic_name);
                return (
                  <li key={t.topic_name}>
                    <strong>{t.topic_name}</strong>{" "}
                    <span className="admin-screen__muted">· {t.accuracy}% right</span>{" "}
                    {topic && (
                      <button type="button" className="admin-screen__link-button" onClick={() => onPractise(topic)}>
                        Practise with THUTOra
                      </button>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </section>
        <section className="today-card">
          <h3 className="today-card__title">
            <span className="icon-chip">
              <TrendingUp size={ICON_BUTTON} aria-hidden="true" />
            </span>
            You're strong in
          </h3>
          {data.strongest_topics.length === 0 ? (
            <p className="admin-screen__muted">Not enough answers yet.</p>
          ) : (
            <ul className="today-list">
              {data.strongest_topics.map((t) => (
                <li key={t.topic_name}>
                  <strong>{t.topic_name}</strong> <span className="admin-screen__muted">· {t.accuracy}% right</span>
                </li>
              ))}
            </ul>
          )}
        </section>
        <section className="today-card">
          <h3 className="today-card__title">
            <span className="icon-chip">
              <ClipboardList size={ICON_BUTTON} aria-hidden="true" />
            </span>
            School work
          </h3>
          {data.work.length === 0 ? (
            <p className="admin-screen__muted">No assignments yet.</p>
          ) : (
            <ul className="today-list">
              {data.work.map((w, i) => (
                <li key={i}>
                  <strong>{w.title}</strong>
                  <div className="admin-screen__muted">
                    {w.due_at && `Due ${new Date(w.due_at).toLocaleDateString()} · `}
                    {workStatus(w)}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
}
