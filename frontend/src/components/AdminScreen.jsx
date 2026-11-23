/*
 * NEW 19 Nov 2026 (ADR-044): THUTOra ADMIN -- school management.
 *
 * For the principal, deputy principal and school admin. Same users and
 * records as TEACH; this is the interface for running the school:
 * an overview with to-dos, learners (add, bulk upload, accounts, parents,
 * consent), classes, staff and roles, notices, and the school's profile
 * and settings. Every rule is enforced on the server (StaffScope, ADR-031).
 */
import { useEffect, useState } from "react";
import {
  Bell,
  IdCard,
  LayoutDashboard,
  LayoutGrid,
  History,
  LogOut,
  School,
  Settings,
  Upload,
  UserPlus,
  Users,
} from "lucide-react";
import { fetchAdminStudents, fetchSchoolMe, fetchSchoolOverview } from "../api";
import { roleSummary } from "../utils/staff";
import { ICON_BUTTON, ICON_NAV } from "./icons";
import NoticesSection from "./NoticesSection";
import ActivityLog from "./ActivityLog";
import SchoolPanel from "./SchoolPanel";
import SchoolSettings from "./SchoolSettings";
import { AddStudentPanel, BulkUploadPanel, RosterPanel } from "./TeacherAdminScreen";
import Wordmark from "./Wordmark";
import ChangePassword from "./ChangePassword";
import HelpCentre from "./HelpCentre"; // ADR-050

const TABS = [
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "learners", label: "Learners", icon: Users },
  { id: "classes", label: "Classes", icon: LayoutGrid },
  { id: "staff", label: "Staff", icon: IdCard },
  { id: "notices", label: "Notices", icon: Bell },
  { id: "settings", label: "School settings", icon: Settings },
  { id: "activity", label: "Activity", icon: History }, // code review 19 Nov #11
];

function StatTile({ label, value, sub }) {
  return (
    <div className="stat-tile">
      <span className="stat-tile__label">{label}</span>
      <span className="stat-tile__value">{value}</span>
      {sub && <span className="stat-tile__sub">{sub}</span>}
    </div>
  );
}

function pct(n, d) {
  return d ? `${Math.round((100 * n) / d)}%` : "—";
}

function OverviewPanel({ token, school, onGo }) {
  const [o, setO] = useState(null);
  const [error, setError] = useState(null);
  useEffect(() => {
    let cancelled = false;
    fetchSchoolOverview(token)
      .then((d) => !cancelled && setO(d))
      .catch((err) => !cancelled && setError(err.message));
    return () => {
      cancelled = true;
    };
  }, [token]);

  if (error) return <div className="admin-screen__error">{error}</div>;
  if (!o) return <p className="admin-screen__muted">Loading…</p>;
  const max = Math.max(1, ...o.learners.by_grade.map((g) => g.count));
  return (
    <div className="admin-overview">
      <h2 className="admin-overview__title">
        <span className="icon-chip">
          <School size={ICON_NAV} aria-hidden="true" />
        </span>
        {school.name}
      </h2>
      <div className="stat-row">
        <StatTile
          label="Learners"
          value={o.learners.active}
          sub={o.learners.inactive ? `${o.learners.inactive} left / switched off` : null}
        />
        <StatTile label="Staff" value={o.staff.active} />
        <StatTile label="Classes" value={o.classes.total} />
        <StatTile
          label="Families signed up"
          value={pct(o.families.with_parent_login, o.learners.active)}
          sub={`${o.families.with_parent_login} of ${o.learners.active} learners`}
        />
      </div>
      <div className="today__grid">
        <section className="today-card">
          <h3 className="today-card__title">To do</h3>
          {o.todos.length === 0 ? (
            <p className="admin-screen__muted">Nothing outstanding. Everything is set up.</p>
          ) : (
            <ul className="today-list">
              {o.todos.map((t) => (
                <li key={t.text}>
                  {t.text}{" "}
                  <button type="button" className="admin-screen__link-button" onClick={() => onGo(t.tab)}>
                    Open {TABS.find((x) => x.id === t.tab)?.label}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
        <section className="today-card">
          <h3 className="today-card__title">Learners by grade</h3>
          {o.learners.by_grade.length === 0 ? (
            <p className="admin-screen__muted">No learners yet.</p>
          ) : (
            <ul className="grade-bars">
              {o.learners.by_grade.map((g) => (
                <li key={g.grade} title={`Grade ${g.grade}: ${g.count} learners`}>
                  <span className="grade-bars__label">Grade {g.grade}</span>
                  <span className="grade-bars__track">
                    <span className="grade-bars__bar" style={{ width: `${(100 * g.count) / max}%` }} />
                  </span>
                  <span className="grade-bars__value">{g.count}</span>
                </li>
              ))}
            </ul>
          )}
          <p className="admin-screen__muted">
            Consent recorded for {o.learners.with_consent} of {o.learners.active} · guardian cellphone on record for{" "}
            {o.families.with_contact}
          </p>
        </section>
      </div>
    </div>
  );
}

function LearnersPanel({ token, onLogout, me, students, loading, error, reload }) {
  const [view, setView] = useState("list");
  return (
    <>
      <div className="progress-filter" role="group" aria-label="Learner tools">
        {[
          ["list", "All learners", Users],
          ["add", "Add a learner", UserPlus],
          ["bulk", "Bulk upload", Upload],
        ].map(([id, label, Icon]) => (
          <button
            key={id}
            type="button"
            className={`progress-filter__chip${view === id ? " progress-filter__chip--active" : ""}`}
            aria-pressed={view === id}
            onClick={() => setView(id)}
          >
            <Icon size={ICON_BUTTON} aria-hidden="true" />
            {label}
          </button>
        ))}
      </div>
      {view === "list" && (
        <RosterPanel
          token={token}
          onChanged={reload}
          students={students}
          loading={loading}
          error={error}
          onRetry={reload}
          me={me}
        />
      )}
      {view === "add" && <AddStudentPanel token={token} onLogout={onLogout} onCreated={reload} />}
      {view === "bulk" && <BulkUploadPanel token={token} onLogout={onLogout} onCreated={reload} />}
    </>
  );
}

export default function AdminScreen({ auth, onLogout, switcher }) {
  const [tab, setTab] = useState("overview");
  const [me, setMe] = useState(null);
  const [students, setStudents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [schoolName, setSchoolName] = useState(auth.school.name);

  const load = async () => {
    setLoading(true);
    try {
      const [m, s] = await Promise.all([fetchSchoolMe(auth.token), fetchAdminStudents(auth.token)]);
      setMe(m);
      setStudents(s);
      setError(null);
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
    const id = setTimeout(load, 0);
    return () => clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="admin-screen" data-product="admin">
      <header className="chat-screen__header">
        <Wordmark product="admin" />
        <div className="chat-screen__header-right">
          {switcher}
          <div className="chat-screen__profile">
            <span className="chat-screen__profile-name">
              {me?.display_name ? `${me.display_name} · ` : ""}
              {roleSummary(me)} — {schoolName}
            </span>
            <HelpCentre token={auth.token} product="admin" />
            <ChangePassword token={auth.token} />
            <button type="button" className="chat-screen__logout" onClick={onLogout}>
              <LogOut size={ICON_BUTTON} aria-hidden="true" />
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
            <span className="icon-chip">
              <t.icon size={ICON_NAV} aria-hidden="true" />
            </span>
            {t.label}
          </button>
        ))}
      </nav>

      <main className="admin-screen__body admin-screen__body--wide">
        {tab === "overview" && (
          <OverviewPanel token={auth.token} school={{ name: schoolName }} onGo={setTab} />
        )}
        {tab === "learners" && (
          <LearnersPanel
            token={auth.token}
            onLogout={onLogout}
            me={me}
            students={students}
            loading={loading}
            error={error}
            reload={load}
          />
        )}
        {(tab === "classes" || tab === "staff") && me && (
          <SchoolPanel
            key={tab}
            only={tab}
            token={auth.token}
            onLogout={onLogout}
            me={me}
            students={students}
            onChanged={load}
          />
        )}
        {tab === "notices" && <NoticesSection token={auth.token} />}
        {tab === "settings" && <SchoolSettings token={auth.token} onRenamed={setSchoolName} />}
        {tab === "activity" && <ActivityLog token={auth.token} />}
      </main>
    </div>
  );
}
