/*
 * NEW 23 Nov 2026 (ADR-051). THUTOra Console -- Zynora's internal tool.
 * Not a school product: schools never see it. Sign-in is email + password +
 * an authenticator code; a session lasts 30 minutes and lives only in this
 * browser tab.
 */
import { useEffect, useState } from "react";
import { Building2, ClipboardCheck, History, Inbox, LogOut, Network, UserCog } from "lucide-react";
import { call, setSessionEndedHandler } from "./api";
import { can } from "./format";
import SignIn from "./SignIn";
import Tickets from "./Tickets";
import Schools from "./Schools";
import Registrations from "./Registrations";
import Officials from "./Officials";
import Audit from "./Audit";
import Staff from "./Staff";

const KEY = "thutora.console.session";

const TABS = [
  { id: "tickets", label: "Tickets", icon: Inbox, min: "agent", Screen: Tickets },
  { id: "schools", label: "Schools", icon: Building2, min: "agent", Screen: Schools },
  { id: "registrations", label: "Registrations", icon: ClipboardCheck, min: "lead", Screen: Registrations },
  { id: "officials", label: "Officials", icon: Network, min: "lead", Screen: Officials },
  { id: "audit", label: "Audit log", icon: History, min: "lead", Screen: Audit },
  { id: "staff", label: "Console staff", icon: UserCog, min: "director", Screen: Staff },
];

function load() {
  try {
    return JSON.parse(sessionStorage.getItem(KEY)) || null;
  } catch {
    return null;
  }
}

function save(session) {
  try {
    if (session) sessionStorage.setItem(KEY, JSON.stringify(session));
    else sessionStorage.removeItem(KEY);
  } catch {
    /* private mode: the session just won't survive a reload */
  }
}

export default function App() {
  const [session, setSession] = useState(load);
  const [notice, setNotice] = useState(null);
  const [tab, setTab] = useState("tickets");

  const signIn = (s) => {
    save(s);
    setSession(s);
    setNotice(null);
  };
  const signOut = (why = null) => {
    save(null);
    setSession(null);
    setNotice(why);
    setTab("tickets");
  };

  useEffect(() => {
    setSessionEndedHandler(() => signOut("Your session ended. Please sign in again."));
  }, []);

  if (!session || session.me.must_change_password) {
    return <SignIn session={session} onSignedIn={signIn} notice={notice} />;
  }

  const { token, me } = session;
  const tabs = TABS.filter((t) => can(me, t.min));
  const active = tabs.find((t) => t.id === tab) || tabs[0];

  const logout = async () => {
    try {
      await call("/auth/logout", { token, method: "POST" });
    } catch {
      /* ending the local session is what matters */
    }
    signOut("You signed out.");
  };

  return (
    <div className="console">
      <header className="console__header">
        <div className="brand">
          <img src="/thutora-core-logo.png" alt="" className="brand__mark" />
          <span className="brand__name">
            THUTO<span className="brand__ra">ra</span>
          </span>
          <span className="brand__badge">CONSOLE</span>
          <span className="brand__internal">Zynora staff only</span>
        </div>
        <div className="console__who">
          <span>
            {me.display_name} · {me.role_label}
          </span>
          <button type="button" className="btn btn--ghost" onClick={logout}>
            <LogOut size={16} aria-hidden="true" /> Sign out
          </button>
        </div>
      </header>
      <nav className="console__tabs" aria-label="Console sections">
        {tabs.map((t) => (
          <button
            key={t.id}
            type="button"
            className={`tab${active.id === t.id ? " tab--active" : ""}`}
            aria-current={active.id === t.id ? "page" : undefined}
            onClick={() => setTab(t.id)}
          >
            <t.icon size={18} aria-hidden="true" />
            {t.label}
          </button>
        ))}
      </nav>
      <main className="console__body">
        <active.Screen token={token} me={me} />
      </main>
    </div>
  );
}
