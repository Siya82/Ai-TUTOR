/*
 * NEW 17 Nov 2026 (ADR-030, TEACH class progress dashboard). The
 * "Progress" tab of TeacherAdminScreen.jsx -- the first UI on top of the
 * /api/v1/dashboard/* data ADR-024 put behind teacher auth.
 *
 * Two views in one panel:
 *   - Class view: summary tiles, learners (riskiest first), and topics
 *     the class has attempted (in CAPS order) with class accuracy.
 *   - Learner view: one learner's per-topic mastery, risk flags with the
 *     risk model's own factors/interventions, and recent misconceptions.
 *
 * Risk is always shown as a text label plus an icon, never colour alone.
 * A learner with no attempts shows "No data yet", deliberately not "Low":
 * no evidence is not the same as low risk.
 */

import { useEffect, useRef, useState } from "react";
import { fetchClassProgress, fetchLearnerProgress } from "../api";

const RISK_META = {
  high: { label: "High", icon: "▲" },
  medium: { label: "Medium", icon: "●" },
  low: { label: "Low", icon: "✓" },
};

function RiskBadge({ level }) {
  if (!level) return <span className="risk-badge risk-badge--none">No data yet</span>;
  const meta = RISK_META[level] || { label: level, icon: "" };
  return (
    <span className={`risk-badge risk-badge--${level}`}>
      <span aria-hidden="true">{meta.icon}</span> {meta.label}
    </span>
  );
}

function AccuracyBar({ value }) {
  if (value === null || value === undefined) {
    return <span className="admin-screen__muted">—</span>;
  }
  const pct = Math.round(value * 100);
  return (
    <span className="accuracy-bar" title={`${pct}% correct`}>
      <span className="accuracy-bar__track">
        <span className="accuracy-bar__fill" style={{ width: `${pct}%` }} />
      </span>
      <span className="accuracy-bar__value">{pct}%</span>
    </span>
  );
}

function formatWhen(iso) {
  if (!iso) return "Never";
  const then = new Date(iso.endsWith("Z") ? iso : `${iso}Z`); // backend stores naive UTC
  const days = Math.floor((Date.now() - then.getTime()) / 86400000);
  if (days <= 0) return "Today";
  if (days === 1) return "Yesterday";
  return `${days} days ago`;
}

function StatTile({ label, value, hint }) {
  return (
    <div className="stat-tile">
      <div className="stat-tile__value">{value}</div>
      <div className="stat-tile__label">{label}</div>
      {hint && <div className="stat-tile__hint">{hint}</div>}
    </div>
  );
}

export default function ProgressPanel({ token, onLogout }) {
  const [grade, setGrade] = useState(null);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedLearnerId, setSelectedLearnerId] = useState(null);
  // Held in a ref so a parent re-render passing a fresh onLogout function
  // never re-triggers the data fetch below.
  const onLogoutRef = useRef(onLogout);
  useEffect(() => {
    onLogoutRef.current = onLogout;
  }, [onLogout]);

  // Bumped by "Refresh"/"Try again" to re-run the fetch effect below.
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    fetchClassProgress(token, grade)
      .then((d) => {
        if (cancelled) return;
        setData(d);
        setError(null);
        setLoading(false);
      })
      .catch((err) => {
        if (cancelled) return;
        if (err.status === 401) {
          onLogoutRef.current();
          return;
        }
        setError(err.message);
        setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [token, grade, reloadKey]);

  const load = () => {
    setLoading(true);
    setReloadKey((k) => k + 1);
  };
  const chooseGrade = (g) => {
    if (g === grade) return;
    setLoading(true);
    setGrade(g);
  };

  if (selectedLearnerId) {
    return (
      <LearnerDetail
        token={token}
        onLogout={onLogout}
        learnerId={selectedLearnerId}
        onBack={() => setSelectedLearnerId(null)}
      />
    );
  }

  if (loading && !data) return <p className="admin-screen__muted">Loading class progress…</p>;
  if (error) {
    return (
      <div className="admin-screen__error">
        {error}{" "}
        <button type="button" className="admin-screen__link-button" onClick={load}>
          Try again
        </button>
      </div>
    );
  }
  if (!data) return null;

  const { summary, learners, topics, available_grades: grades } = data;
  const pct = (v) => (v === null || v === undefined ? "—" : `${Math.round(v * 100)}%`);

  return (
    <div className="admin-panel">
      <div className="progress-toolbar">
        <div className="progress-filter" role="group" aria-label="Filter by grade">
          <button
            type="button"
            className={`progress-filter__chip${grade === null ? " progress-filter__chip--active" : ""}`}
            onClick={() => chooseGrade(null)}
          >
            All grades
          </button>
          {grades.map((g) => (
            <button
              key={g}
              type="button"
              className={`progress-filter__chip${grade === g ? " progress-filter__chip--active" : ""}`}
              onClick={() => chooseGrade(g)}
            >
              Grade {g}
            </button>
          ))}
        </div>
        <button type="button" className="admin-screen__link-button" onClick={load} disabled={loading}>
          {loading ? "Refreshing…" : "Refresh"}
        </button>
      </div>

      <div className="stat-tiles">
        <StatTile label="Learners" value={summary.total_learners} />
        <StatTile
          label="Active"
          value={summary.active_learners}
          hint={`answered in the last ${summary.active_window_days} days`}
        />
        <StatTile label="High risk" value={summary.high_risk_learners} />
        <StatTile label="Medium risk" value={summary.medium_risk_learners} />
        <StatTile label="Not started" value={summary.learners_with_no_attempts} hint="no answers yet" />
        <StatTile label="Class accuracy" value={pct(summary.class_accuracy)} />
      </div>

      <section>
        <h3 className="admin-screen__subheading">Learners</h3>
        {learners.length === 0 ? (
          <p className="admin-screen__muted">No learners in this grade yet.</p>
        ) : (
          <table className="admin-table progress-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Grade</th>
                <th>Risk</th>
                <th>Accuracy</th>
                <th>Answers</th>
                <th>Last active</th>
                <th>Needs attention on</th>
              </tr>
            </thead>
            <tbody>
              {learners.map((l) => (
                <tr
                  key={l.id}
                  className="progress-table__row"
                  tabIndex={0}
                  onClick={() => setSelectedLearnerId(l.id)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      setSelectedLearnerId(l.id);
                    }
                  }}
                  title="Open this learner's progress"
                >
                  <td className="progress-table__name">{l.name}</td>
                  <td>{l.grade}</td>
                  <td>
                    <RiskBadge level={l.risk_level} />
                  </td>
                  <td>
                    <AccuracyBar value={l.overall_accuracy} />
                  </td>
                  <td>{l.total_attempts}</td>
                  <td>{formatWhen(l.last_activity)}</td>
                  <td className="progress-table__flags">
                    {l.flagged_topics.length === 0
                      ? "—"
                      : l.flagged_topics.slice(0, 2).map((f) => f.topic_name).join(", ") +
                        (l.flagged_topics.length > 2 ? ` +${l.flagged_topics.length - 2} more` : "")}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section>
        <h3 className="admin-screen__subheading">Topics</h3>
        {topics.length === 0 ? (
          <p className="admin-screen__muted">
            No answers recorded yet. Topic results appear here once learners complete assignments.
          </p>
        ) : (
          <table className="admin-table progress-table">
            <thead>
              <tr>
                <th>Topic</th>
                <th>Class accuracy</th>
                <th>Learners</th>
                <th>Answers</th>
                <th>Struggling</th>
              </tr>
            </thead>
            <tbody>
              {topics.map((t) => (
                <tr key={t.topic_id}>
                  <td>
                    <div className="progress-table__name">{t.topic_name}</div>
                    <div className="admin-screen__muted">
                      Grade {t.grade} · {t.subject_name}
                    </div>
                  </td>
                  <td>
                    <AccuracyBar value={t.accuracy} />
                  </td>
                  <td>{t.learners_attempted}</td>
                  <td>{t.attempt_count}</td>
                  <td>
                    {t.struggling_learners > 0 ? (
                      <span className="risk-badge risk-badge--medium">
                        <span aria-hidden="true">●</span> {t.struggling_learners}
                      </span>
                    ) : (
                      "0"
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <p className="admin-screen__muted">
          "Struggling" means below 60% on that topic over at least 2 answers.
        </p>
      </section>
    </div>
  );
}

function LearnerDetail({ token, onLogout, learnerId, onBack }) {
  const [detail, setDetail] = useState(null);
  const [error, setError] = useState(null);
  const onLogoutRef = useRef(onLogout);
  useEffect(() => {
    onLogoutRef.current = onLogout;
  }, [onLogout]);

  useEffect(() => {
    let cancelled = false;
    fetchLearnerProgress(token, learnerId)
      .then((d) => {
        if (!cancelled) setDetail(d);
      })
      .catch((err) => {
        if (cancelled) return;
        if (err.status === 401) {
          onLogoutRef.current();
          return;
        }
        setError(err.message);
      });
    return () => {
      cancelled = true;
    };
  }, [token, learnerId]);

  const back = (
    <button type="button" className="admin-screen__link-button progress-back" onClick={onBack}>
      ← Back to class
    </button>
  );

  if (error) {
    return (
      <div className="admin-panel">
        {back}
        <div className="admin-screen__error">{error}</div>
      </div>
    );
  }
  if (!detail) return <p className="admin-screen__muted">Loading learner…</p>;

  const { learner, mastery, risk_assessments: risks } = detail;
  const flagged = risks.filter((r) => r.risk_level !== "low");

  return (
    <div className="admin-panel">
      {back}
      <div>
        <h3 className="admin-screen__subheading">{learner.name}</h3>
        <p className="admin-screen__muted">Grade {learner.grade}</p>
      </div>

      <section>
        <h4 className="progress-section-title">Needs attention</h4>
        {flagged.length === 0 ? (
          <p className="admin-screen__muted">
            {mastery.topics.length === 0
              ? "No answers yet, so there's nothing to assess."
              : "Nothing flagged by the early-warning model."}
          </p>
        ) : (
          <div className="risk-cards">
            {flagged.map((r) => (
              <div key={r.topic_id} className={`risk-card risk-card--${r.risk_level}`}>
                <div className="risk-card__header">
                  <span className="progress-table__name">{r.topic_name}</span>
                  <RiskBadge level={r.risk_level} />
                </div>
                {r.grade && (
                  <div className="admin-screen__muted">
                    Grade {r.grade} · {r.subject_name}
                  </div>
                )}
                <ul className="risk-card__list">
                  {r.factors.map((f) => (
                    <li key={f}>{f}</li>
                  ))}
                </ul>
                {r.interventions.length > 0 && (
                  <div className="risk-card__action">
                    <strong>Suggested:</strong> {r.interventions.join(" ")}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </section>

      <section>
        <h4 className="progress-section-title">Mastery by topic</h4>
        {mastery.topics.length === 0 ? (
          <p className="admin-screen__muted">No answers recorded yet.</p>
        ) : (
          <table className="admin-table progress-table">
            <thead>
              <tr>
                <th>Topic</th>
                <th>Accuracy</th>
                <th>Answers</th>
                <th>Last answered</th>
              </tr>
            </thead>
            <tbody>
              {mastery.topics.map((t) => (
                <tr key={t.topic_id}>
                  <td>
                    <div className="progress-table__name">{t.topic_name}</div>
                    {t.grade && (
                      <div className="admin-screen__muted">
                        Grade {t.grade} · {t.subject_name}
                      </div>
                    )}
                  </td>
                  <td>
                    <AccuracyBar value={t.accuracy} />
                  </td>
                  <td>{t.attempt_count}</td>
                  <td>{formatWhen(t.last_attempt)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section>
        <h4 className="progress-section-title">Recent mistakes</h4>
        {mastery.recent_misconceptions.length === 0 ? (
          <p className="admin-screen__muted">No incorrect answers with feedback yet.</p>
        ) : (
          <ul className="misconception-list">
            {mastery.recent_misconceptions.map((m, i) => (
              <li key={i} className="misconception-list__item">
                <div className="admin-screen__muted">{m.topic}</div>
                <div className="misconception-list__question">{m.question}</div>
                <div>{m.feedback}</div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
