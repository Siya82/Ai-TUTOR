/*
 * NEW 19 Nov 2026 (ADR-044). Staff land here after login. One identity, one
 * school database -- two interfaces: TEACH for teaching, ADMIN for running
 * the school. People who do both (e.g. a principal who teaches Maths) switch
 * with the TEACH | ADMIN control in the header.
 */
import { lazy, Suspense, useEffect, useState } from "react";
import { fetchSchoolMe } from "../api";
import { defaultWorkspace, WORKSPACE_KEY } from "../utils/staff";
// deep scan M6: a teacher who never opens ADMIN never downloads it
const AdminScreen = lazy(() => import("./AdminScreen"));
const TeacherAdminScreen = lazy(() => import("./TeacherAdminScreen"));

function readStored() {
  try {
    return localStorage.getItem(WORKSPACE_KEY);
  } catch {
    return null;
  }
}

export function WorkspaceSwitch({ value, onChange }) {
  return (
    <div className="workspace-switch" role="group" aria-label="Workspace">
      {["teach", "admin"].map((w) => (
        <button
          key={w}
          type="button"
          data-product={w}
          aria-pressed={value === w}
          className={`workspace-switch__option${value === w ? " workspace-switch__option--active" : ""}`}
          onClick={() => onChange(w)}
        >
          {w.toUpperCase()}
        </button>
      ))}
    </div>
  );
}

export default function StaffWorkspace({ auth, onLogout }) {
  const [me, setMe] = useState(null);
  const [workspace, setWorkspace] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    fetchSchoolMe(auth.token)
      .then((loaded) => {
        if (cancelled) return;
        setMe(loaded);
        setWorkspace(defaultWorkspace(loaded, readStored()));
      })
      .catch((err) => {
        if (cancelled) return;
        if (err.status === 401) onLogout();
        else setError(err.message);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- once per login
  }, [auth.token]);

  if (error) {
    return (
      <div className="app-loading">
        {error}{" "}
        <button type="button" className="admin-screen__link-button" onClick={onLogout}>
          Log out
        </button>
      </div>
    );
  }
  if (!me || !workspace) return <div className="app-loading">Loading…</div>;

  const choose = (w) => {
    setWorkspace(w);
    try {
      localStorage.setItem(WORKSPACE_KEY, w);
    } catch {
      /* private mode: just don't remember */
    }
  };
  const both = me.can_manage_school && me.has_academic_access;
  const switcher = both ? <WorkspaceSwitch value={workspace} onChange={choose} /> : null;

  return (
    <Suspense fallback={<div className="app-loading">Loading…</div>}>
      {workspace === "admin" ? (
        <AdminScreen auth={auth} onLogout={onLogout} switcher={switcher} />
      ) : (
        <TeacherAdminScreen auth={auth} onLogout={onLogout} switcher={switcher} />
      )}
    </Suspense>
  );
}
