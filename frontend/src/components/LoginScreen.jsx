/*
 * NEW 14 Nov 2026 (ADR-017, student login). School + student number +
 * password login, with a forced "set your own password" step when the
 * student is logging in with a temporary password for the first time
 * (must_change_password). See App.jsx for how the resulting session
 * (token + learner + school) is stored and handed to ChatScreen.
 *
 * "Remember password" (Siya's request, same day): deliberately NOT a
 * custom localStorage password store -- that'd mean a plaintext
 * password sitting in browser storage on what may well be a shared
 * school/lab device, which is a much worse POPIA posture than this
 * app already took a stance on in the ADR. Instead the student
 * number/password fields carry the right `name`/`autoComplete`
 * tokens so the browser's OWN password manager (Chrome/Edge/etc, or
 * the OS keychain it's backed by) recognizes this as a login form and
 * offers its native "save password?" prompt + autofill -- the
 * password itself never touches THUTOra's own code or storage either
 * way. Unmounting this form on a successful login (App.jsx swaps to
 * ChatScreen) is exactly the signal most browsers' save-password
 * heuristic looks for.
 */

import { useEffect, useState } from "react";
import { changePassword, fetchSchools, login } from "../api";

export default function LoginScreen({ onLogin }) {
  const [schools, setSchools] = useState([]);
  const [schoolId, setSchoolId] = useState("");
  const [studentNumber, setStudentNumber] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [loadError, setLoadError] = useState(null);

  // Holds the just-logged-in session (token + learner + school) while
  // must_change_password is true, so the form below can complete the
  // login with a new password instead of asking the student to log in
  // a second time right after setting one.
  const [pendingSession, setPendingSession] = useState(null);
  const [newPassword, setNewPassword] = useState("");
  const [newPasswordConfirm, setNewPasswordConfirm] = useState("");
  const [changing, setChanging] = useState(false);
  const [changeError, setChangeError] = useState(null);

  useEffect(() => {
    (async () => {
      try {
        const fetchedSchools = await fetchSchools();
        setSchools(fetchedSchools);
        if (fetchedSchools.length > 0) setSchoolId(fetchedSchools[0].id);
        else setLoadError("No schools are set up yet. Run backend/scripts/seed_dev_data.py, or ask THUTOra to add one.");
      } catch (err) {
        setLoadError(`Could not reach the backend at http://localhost:8000 (${err.message}). Is uvicorn running?`);
      }
    })();
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!schoolId || !studentNumber.trim() || !password || loading) return;
    setLoading(true);
    setError(null);
    try {
      const response = await login({ schoolId, studentNumber: studentNumber.trim(), password });
      if (response.must_change_password) {
        setPendingSession(response);
      } else {
        onLogin(response);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleChangePassword = async (e) => {
    e.preventDefault();
    if (!pendingSession || changing) return;
    if (newPassword.length < 8) {
      setChangeError("Choose a password at least 8 characters long.");
      return;
    }
    if (newPassword !== newPasswordConfirm) {
      setChangeError("Those two passwords don't match.");
      return;
    }
    setChanging(true);
    setChangeError(null);
    try {
      await changePassword({
        token: pendingSession.access_token,
        currentPassword: password,
        newPassword,
      });
      onLogin({ ...pendingSession, must_change_password: false });
    } catch (err) {
      setChangeError(err.message);
    } finally {
      setChanging(false);
    }
  };

  const brand = (
    <div className="login-screen__brand">
      <img src="/thutora-logo.png" alt="" className="login-screen__brand-logo" />
      THUTOra<span className="login-screen__brand-dot">.</span>
    </div>
  );

  if (pendingSession) {
    return (
      <div className="login-screen">
        <div className="login-screen__card">
          {brand}
          <h1 className="login-screen__title">Choose a new password</h1>
          <p className="login-screen__subtitle">
            You logged in with a temporary password — set your own before continuing.
          </p>
          <form className="login-screen__form" onSubmit={handleChangePassword} autoComplete="on">
            <label className="login-screen__field">
              <span>New password</span>
              <input
                type="password"
                name="new-password"
                autoComplete="new-password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                minLength={8}
                required
                autoFocus
              />
            </label>
            <label className="login-screen__field">
              <span>Confirm new password</span>
              <input
                type="password"
                name="new-password-confirm"
                autoComplete="new-password"
                value={newPasswordConfirm}
                onChange={(e) => setNewPasswordConfirm(e.target.value)}
                minLength={8}
                required
              />
            </label>
            {changeError && <div className="login-screen__error">{changeError}</div>}
            <button type="submit" disabled={changing}>
              {changing ? "Saving…" : "Set password and continue"}
            </button>
          </form>
        </div>
      </div>
    );
  }

  return (
    <div className="login-screen">
      <div className="login-screen__card">
        {brand}
        <h1 className="login-screen__title">Log in</h1>
        {loadError && <div className="login-screen__error">{loadError}</div>}
        <form className="login-screen__form" onSubmit={handleSubmit} autoComplete="on">
          <label className="login-screen__field">
            <span>School</span>
            <select
              name="organization"
              value={schoolId}
              onChange={(e) => setSchoolId(e.target.value)}
              disabled={schools.length === 0}
            >
              {schools.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </label>
          <label className="login-screen__field">
            <span>Student number</span>
            <input
              type="text"
              name="username"
              autoComplete="username"
              value={studentNumber}
              onChange={(e) => setStudentNumber(e.target.value)}
              autoFocus
              required
            />
          </label>
          <label className="login-screen__field">
            <span>Password</span>
            <input
              type="password"
              name="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </label>
          {error && <div className="login-screen__error">{error}</div>}
          <button type="submit" disabled={loading || schools.length === 0}>
            {loading ? "Logging in…" : "Log in"}
          </button>
        </form>
      </div>
    </div>
  );
}
