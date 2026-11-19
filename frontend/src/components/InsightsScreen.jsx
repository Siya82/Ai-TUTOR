/*
 * NEW 19 Nov 2026 (ADR-039, INSIGHTS). The circuit/district official's view:
 * learning outcomes for every school in their area over the last 30 days --
 * participation, accuracy and a plain-language band per school, the weakest
 * topics across the area, and a drill-down into one school by grade/subject,
 * topic and class. Aggregates only: no learner is ever named, and groups
 * with fewer than 5 learners are shown as "too few learners".
 */
import { useEffect, useState } from "react";
import { ArrowLeft, LogOut, MapPinned, School as SchoolIcon, TrendingDown } from "lucide-react";
import { fetchInsightsOverview, fetchInsightsSchool, fetchInsightsScope } from "../api";
import { ICON_BUTTON, ICON_NAV } from "./icons";
import PrivacyNotice from "./PrivacyNotice";

// "Umgungundlovu" -> "Umgungundlovu District", but "Demo District" stays as is
const withSuffix = (name, word) => (name.toLowerCase().endsWith(word.toLowerCase()) ? name : `${name} ${word}`);

const BAND_LABEL = { good: "Good", watch: "Watch", concern: "Concern" };

function Band({ row }) {
  if (row.suppressed) return <span className="admin-screen__muted">Too few learners</span>;
  if (row.accuracy == null) return <span className="admin-screen__muted">No answers yet</span>;
  return (
    <span className={`insights-band insights-band--${row.band}`}>
      {BAND_LABEL[row.band]} · {row.accuracy}%
    </span>
  );
}

function Bar({ value }) {
  if (value == null) return null;
  return (
    <span className="insights-bar" aria-hidden="true">
      <span className="insights-bar__fill" style={{ width: `${Math.max(2, Math.min(100, value))}%` }} />
    </span>
  );
}

function TopicList({ topics }) {
  if (!topics.length) {
    return <p className="admin-screen__muted">Not enough answers yet to rank topics.</p>;
  }
  return (
    <ul className="today-list">
      {topics.map((t) => (
        <li key={t.key} className="today-list__row">
          <div>
            <strong>{t.label}</strong>
            <div className="admin-screen__muted">
              Grade {t.grade} {t.subject}
              {t.schools ? ` · ${t.schools} school${t.schools === 1 ? "" : "s"}` : ""} · {t.answered} answers
            </div>
          </div>
          <Band row={t} />
        </li>
      ))}
    </ul>
  );
}

export default function InsightsScreen({ auth, onLogout }) {
  const [scope, setScope] = useState(null);
  const [circuitId, setCircuitId] = useState("");
  const [overview, setOverview] = useState(null);
  const [schoolId, setSchoolId] = useState(null);
  const [school, setSchool] = useState(null);
  const [error, setError] = useState(null);
  const [showPrivacy, setShowPrivacy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const id = setTimeout(() => {
      fetchInsightsScope(auth.token)
        .then((s) => !cancelled && setScope(s))
        .catch((err) => !cancelled && setError(err.message));
    }, 0);
    return () => {
      cancelled = true;
      clearTimeout(id);
    };
  }, [auth.token]);

  useEffect(() => {
    let cancelled = false;
    const id = setTimeout(() => {
      setOverview(null);
      fetchInsightsOverview(auth.token, circuitId)
        .then((o) => !cancelled && setOverview(o))
        .catch((err) => !cancelled && setError(err.message));
    }, 0);
    return () => {
      cancelled = true;
      clearTimeout(id);
    };
  }, [auth.token, circuitId]);

  useEffect(() => {
    if (!schoolId) return undefined;
    let cancelled = false;
    const id = setTimeout(() => {
      setSchool(null);
      fetchInsightsSchool(auth.token, schoolId)
        .then((d) => !cancelled && setSchool(d))
        .catch((err) => !cancelled && setError(err.message));
    }, 0);
    return () => {
      cancelled = true;
      clearTimeout(id);
    };
  }, [auth.token, schoolId]);

  const area =
    scope &&
    (scope.district_level
      ? scope.districts.map((d) => withSuffix(d.name, "District")).join(", ")
      : scope.circuits.map((c) => withSuffix(c.name, "Circuit")).join(", "));

  return (
    <div className="admin-screen" data-product="insights">
      <header className="chat-screen__header">
        <div className="chat-screen__brand">
          <img src="/thutora-insights-logo.png" alt="" className="chat-screen__brand-logo" />
          THUTOra
          <span className="product-badge">INSIGHTS</span>
        </div>
        <div className="chat-screen__header-right">
          <div className="chat-screen__profile">
            <span className="chat-screen__profile-name">
              {scope?.display_name ? `${scope.display_name} · ` : ""}
              {area}
            </span>
            <button type="button" className="chat-screen__logout" onClick={onLogout}>
              <LogOut size={ICON_BUTTON} aria-hidden="true" />
              Log out
            </button>
          </div>
        </div>
      </header>

      <main className="admin-screen__body admin-screen__body--wide">
        {error && <div className="admin-screen__error">{error}</div>}

        {schoolId ? (
          <>
            <button type="button" className="admin-screen__link-button insights-back" onClick={() => setSchoolId(null)}>
              <ArrowLeft size={16} aria-hidden="true" /> All schools
            </button>
            {!school ? (
              <p className="admin-screen__muted">Loading school…</p>
            ) : (
              <>
                <h2 className="insights-title">
                  <span className="icon-chip">
                    <SchoolIcon size={ICON_NAV} aria-hidden="true" />
                  </span>
                  {school.school.name}
                </h2>
                <p className="admin-screen__muted">Last {school.window_days} days.</p>
                <div className="today__grid">
                  <section className="today-card">
                    <h3 className="today-card__title">By grade and subject</h3>
                    <table className="admin-table">
                      <tbody>
                        {school.by_grade_subject.map((r) => (
                          <tr key={r.key}>
                            <td>{r.label}</td>
                            <td>
                              <Bar value={r.accuracy} />
                            </td>
                            <td>
                              <Band row={r} />
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </section>
                  <section className="today-card">
                    <h3 className="today-card__title">Weakest topics</h3>
                    <TopicList topics={school.weakest_topics} />
                  </section>
                  <section className="today-card">
                    <h3 className="today-card__title">Classes</h3>
                    {school.classes.length === 0 ? (
                      <p className="admin-screen__muted">This school hasn't set up classes yet.</p>
                    ) : (
                      <table className="admin-table">
                        <tbody>
                          {school.classes.map((r) => (
                            <tr key={r.key}>
                              <td>{r.label}</td>
                              <td>
                                <Band row={r} />
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )}
                  </section>
                </div>
              </>
            )}
          </>
        ) : (
          <>
            {scope && scope.circuits.length > 1 && (
              <div className="progress-filter" role="tablist" aria-label="Circuit">
                {[{ id: "", name: "All circuits" }, ...scope.circuits].map((c) => (
                  <button
                    key={c.id || "all"}
                    type="button"
                    className={`progress-filter__chip${circuitId === c.id ? " progress-filter__chip--active" : ""}`}
                    onClick={() => setCircuitId(c.id)}
                  >
                    {c.name}
                  </button>
                ))}
              </div>
            )}
            {!overview ? (
              <p className="admin-screen__muted">Loading…</p>
            ) : overview.schools.length === 0 ? (
              <p className="admin-screen__muted">
                No schools are linked to your area in THUTOra yet. Zynora links schools to circuits during onboarding.
              </p>
            ) : (
              <>
                {overview.totals && (
                  <div className="insights-kpis">
                    <div className="insights-kpi">
                      <span className="insights-kpi__value">{overview.schools.length}</span>
                      <span className="admin-screen__muted">schools</span>
                    </div>
                    <div className="insights-kpi">
                      <span className="insights-kpi__value">{overview.totals.learners_enrolled}</span>
                      <span className="admin-screen__muted">learners</span>
                    </div>
                    <div className="insights-kpi">
                      <span className="insights-kpi__value">
                        {overview.totals.participation == null ? "—" : `${overview.totals.participation}%`}
                      </span>
                      <span className="admin-screen__muted">practised in {overview.window_days} days</span>
                    </div>
                    <div className="insights-kpi">
                      <span className="insights-kpi__value">
                        {overview.totals.accuracy == null ? "—" : `${overview.totals.accuracy}%`}
                      </span>
                      <span className="admin-screen__muted">answers right</span>
                    </div>
                  </div>
                )}
                <div className="today__grid">
                  <section className="today-card insights-schools">
                    <h3 className="today-card__title">
                      <span className="icon-chip">
                        <MapPinned size={ICON_BUTTON} aria-hidden="true" />
                      </span>
                      Schools
                    </h3>
                    <table className="admin-table">
                      <thead>
                        <tr>
                          <th>School</th>
                          {scope?.circuits.length > 1 && <th>Circuit</th>}
                          <th>Practising</th>
                          <th>Accuracy</th>
                        </tr>
                      </thead>
                      <tbody>
                        {overview.schools.map((s) => (
                          <tr key={s.key}>
                            <td>
                              <button
                                type="button"
                                className="admin-screen__link-button"
                                onClick={() => setSchoolId(s.key)}
                              >
                                {s.label}
                              </button>
                            </td>
                            {scope?.circuits.length > 1 && <td>{s.circuit}</td>}
                            <td>
                              {s.participation == null ? "—" : `${s.participation}%`}{" "}
                              <span className="admin-screen__muted">of {s.learners_enrolled}</span>
                            </td>
                            <td>
                              <Bar value={s.accuracy} /> <Band row={s} />
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </section>
                  <section className="today-card">
                    <h3 className="today-card__title">
                      <span className="icon-chip">
                        <TrendingDown size={ICON_BUTTON} aria-hidden="true" />
                      </span>
                      Weakest topics across these schools
                    </h3>
                    <TopicList topics={overview.weakest_topics} />
                  </section>
                </div>
              </>
            )}
          </>
        )}
        <p className="admin-screen__muted insights-footnote">
          Figures cover the last 30 days of marked answers in THUTOra. No learner is named, and any group with fewer
          than 5 learners is hidden.{" "}
          <button type="button" className="privacy-link" onClick={() => setShowPrivacy(true)}>
            Privacy notice
          </button>
        </p>
        {showPrivacy && <PrivacyNotice onClose={() => setShowPrivacy(false)} />}
      </main>
    </div>
  );
}
