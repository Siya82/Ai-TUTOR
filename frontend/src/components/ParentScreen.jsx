/*
 * NEW 19 Nov 2026 (ADR-038, CONNECT). What a parent/guardian sees: their
 * child's week (how much they practised, how often right, strongest and
 * weakest topics), their school work and released marks, and the school's
 * notices -- with a short summary they can read in their own language.
 * Children's tutor conversations are never shown here.
 */
import { useEffect, useState } from "react";
import { Bell, ClipboardList, Languages, LogOut, TrendingUp } from "lucide-react";
import {
  acknowledgeNotice,
  fetchChildOverview,
  fetchChildSummary,
  fetchHomeLanguages,
  fetchMyChildren,
  fetchParentNotices,
} from "../api";
import { ICON_BUTTON, ICON_NAV } from "./icons";
import PrivacyNotice from "./PrivacyNotice";
import Wordmark from "./Wordmark";
import FamilyAccess from "./FamilyAccess";

const LANG_KEY = "thutora_parent_language";

function statusLabel(w) {
  if (w.status === "completed") {
    return w.marks_earned == null
      ? "Done (marks not released yet)"
      : `Done — ${w.marks_earned}/${w.marks_total}`;
  }
  return w.status === "in_progress" ? "Started" : "Not started";
}

export default function ParentScreen({ auth, onLogout }) {
  const [children, setChildren] = useState(null);
  const [childId, setChildId] = useState(null);
  const [overview, setOverview] = useState(null);
  const [summary, setSummary] = useState(null);
  const [languages, setLanguages] = useState(["English"]);
  const [language, setLanguage] = useState(() => {
    try {
      return localStorage.getItem(LANG_KEY) || "English";
    } catch {
      return "English";
    }
  });
  const [notices, setNotices] = useState([]);
  const [tab, setTab] = useState("progress");
  const [error, setError] = useState(null);
  const [showPrivacy, setShowPrivacy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const id = setTimeout(() => {
      fetchMyChildren(auth.token)
        .then((list) => {
          if (cancelled) return;
          setChildren(list);
          if (list.length) setChildId(list[0].learner_id);
        })
        .catch((err) => !cancelled && setError(err.message));
      fetchParentNotices(auth.token)
        .then((n) => !cancelled && setNotices(n))
        .catch(() => {});
      fetchHomeLanguages()
        .then((l) => !cancelled && setLanguages(l))
        .catch(() => {});
    }, 0);
    return () => {
      cancelled = true;
      clearTimeout(id);
    };
  }, [auth.token]);

  useEffect(() => {
    if (!childId) return undefined;
    let cancelled = false;
    const id = setTimeout(() => {
      setOverview(null);
      fetchChildOverview(auth.token, childId)
        .then((o) => !cancelled && setOverview(o))
        .catch((err) => !cancelled && setError(err.message));
    }, 0);
    return () => {
      cancelled = true;
      clearTimeout(id);
    };
  }, [auth.token, childId]);

  useEffect(() => {
    if (!childId) return undefined;
    let cancelled = false;
    const id = setTimeout(() => {
      setSummary(null);
      fetchChildSummary(auth.token, childId, language)
        .then((s) => !cancelled && setSummary(s))
        .catch(() => !cancelled && setSummary(null));
    }, 0);
    return () => {
      cancelled = true;
      clearTimeout(id);
    };
  }, [auth.token, childId, language]);

  const changeLanguage = (l) => {
    setLanguage(l);
    try {
      localStorage.setItem(LANG_KEY, l);
    } catch {
      /* fine */
    }
  };

  const ack = async (n) => {
    try {
      await acknowledgeNotice(auth.token, n.id);
      setNotices((list) => list.map((x) => (x.id === n.id ? { ...x, acknowledged: true } : x)));
    } catch (err) {
      setError(err.message);
    }
  };

  const unread = notices.filter((n) => n.requires_ack && !n.acknowledged).length;

  return (
    <div className="admin-screen" data-product="connect">
      <header className="chat-screen__header">
        <Wordmark product="connect" />
        <div className="chat-screen__header-right">
          <div className="chat-screen__profile">
            <span className="chat-screen__profile-name">{auth.school?.name}</span>
            <button type="button" className="chat-screen__logout" onClick={onLogout}>
              <LogOut size={ICON_BUTTON} aria-hidden="true" />
              Log out
            </button>
          </div>
        </div>
      </header>

      <nav className="admin-screen__tabs" aria-label="Sections">
        {[
          ["progress", "My child", TrendingUp],
          ["notices", unread ? `Notices (${unread})` : "Notices", Bell],
        ].map(([id, label, Icon]) => (
          <button
            key={id}
            type="button"
            className={`admin-screen__tab${tab === id ? " admin-screen__tab--active" : ""}`}
            onClick={() => setTab(id)}
          >
            <span className="icon-chip">
              <Icon size={ICON_NAV} aria-hidden="true" />
            </span>
            {label}
          </button>
        ))}
      </nav>

      <main className="admin-screen__body">
        {error && <div className="admin-screen__error">{error}</div>}

        {tab === "progress" && (
          <>
            {children === null ? (
              <p className="admin-screen__muted">Loading…</p>
            ) : children.length === 0 ? (
              <p className="admin-screen__muted">
                No children are linked to your login yet. Please ask the school to link your child.
              </p>
            ) : (
              <>
                <div className="parent-toolbar">
                  {children.length > 1 && (
                    <label className="admin-form__field">
                      <span>Child</span>
                      <select value={childId || ""} onChange={(e) => setChildId(e.target.value)}>
                        {children.map((c) => (
                          <option key={c.learner_id} value={c.learner_id}>
                            {c.display_name} (Grade {c.grade})
                          </option>
                        ))}
                      </select>
                    </label>
                  )}
                  <label className="admin-form__field">
                    <span>
                      <Languages size={14} aria-hidden="true" /> Read in
                    </span>
                    <select value={language} onChange={(e) => changeLanguage(e.target.value)}>
                      {languages.map((l) => (
                        <option key={l}>{l}</option>
                      ))}
                    </select>
                  </label>
                </div>

                <section className="today-card parent-summary">
                  <h3 className="today-card__title">This week</h3>
                  {summary ? (
                    <>
                      <p>{summary.text}</p>
                      {summary.translation_failed && (
                        <p className="admin-screen__muted">Translation isn't available right now, so this is in English.</p>
                      )}
                      {summary.english && summary.language !== "English" && (
                        <details>
                          <summary className="admin-screen__muted">Show in English</summary>
                          <p>{summary.english}</p>
                        </details>
                      )}
                    </>
                  ) : (
                    <p className="admin-screen__muted">Preparing the summary…</p>
                  )}
                </section>

                {overview && (
                  <div className="today__grid">
                    <section className="today-card">
                      <h3 className="today-card__title">
                        <span className="icon-chip">
                          <TrendingUp size={ICON_BUTTON} aria-hidden="true" />
                        </span>
                        Topics
                      </h3>
                      {overview.strongest_topics.length === 0 && overview.weakest_topics.length === 0 ? (
                        <p className="admin-screen__muted">Not enough practice yet to show topics.</p>
                      ) : (
                        <ul className="today-list">
                          {overview.strongest_topics.map((t) => (
                            <li key={`s-${t.topic_name}`}>
                              <span className="consent-badge consent-badge--yes">Strong</span> {t.topic_name}{" "}
                              <span className="admin-screen__muted">· {t.accuracy}% right</span>
                            </li>
                          ))}
                          {overview.weakest_topics.map((t) => (
                            <li key={`w-${t.topic_name}`}>
                              <span className="consent-badge consent-badge--no">Practise</span> {t.topic_name}{" "}
                              <span className="admin-screen__muted">· {t.accuracy}% right</span>
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
                      {overview.work.length === 0 ? (
                        <p className="admin-screen__muted">No assignments yet.</p>
                      ) : (
                        <ul className="today-list">
                          {overview.work.map((w, i) => (
                            <li key={i}>
                              <strong>{w.title}</strong>
                              <div className="admin-screen__muted">
                                {w.subjects.join(", ")}
                                {w.due_at && ` · due ${new Date(w.due_at).toLocaleDateString()}`} · {statusLabel(w)}
                              </div>
                            </li>
                          ))}
                        </ul>
                      )}
                    </section>
                  </div>
                )}
                {/* ADR-043 */}
                {children.find((c) => c.learner_id === childId) && (
                  <FamilyAccess
                    token={auth.token}
                    child={children.find((c) => c.learner_id === childId)}
                    schoolName={auth.school?.name || "your child's school"}
                  />
                )}
              </>
            )}
          </>
        )}

        {tab === "notices" && (
          <div className="parent-notices">
            {notices.length === 0 ? (
              <p className="admin-screen__muted">No notices from the school yet.</p>
            ) : (
              notices.map((n) => (
                <article key={n.id} className="today-card">
                  <h3 className="today-card__title">{n.title}</h3>
                  <p className="admin-screen__muted">
                    {n.created_at && new Date(n.created_at).toLocaleDateString()}
                    {n.grade ? ` · Grade ${n.grade}` : ""}
                  </p>
                  <p className="parent-notices__body">{n.body}</p>
                  {n.requires_ack &&
                    (n.acknowledged ? (
                      <span className="today-list__done">You acknowledged this</span>
                    ) : (
                      <button type="button" className="today-list__action" onClick={() => ack(n)}>
                        I've read this
                      </button>
                    ))}
                </article>
              ))
            )}
          </div>
        )}
        <button type="button" className="privacy-link" onClick={() => setShowPrivacy(true)}>
          Privacy notice
        </button>
        {showPrivacy && <PrivacyNotice onClose={() => setShowPrivacy(false)} />}
      </main>
    </div>
  );
}
