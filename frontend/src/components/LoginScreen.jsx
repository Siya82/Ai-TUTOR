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
import {
  changePassword,
  fetchSchools,
  fetchSignupAvailable,
  login,
} from "../api";
import ParentSignup from "./ParentSignup";
import RegisterSchool from "./RegisterSchool";
import PrivacyNotice from "./PrivacyNotice";
import Wordmark from "./Wordmark";

export default function LoginScreen({ onLogin, notice }) {
  const [schools, setSchools] = useState([]);
  const [showPrivacy, setShowPrivacy] = useState(false); // ADR-037
  const [schoolId, setSchoolId] = useState("");
  const [studentNumber, setStudentNumber] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [loadError, setLoadError] = useState(null);
  const [familyMode, setFamilyMode] = useState(null); // ADR-043: null | "signup" | "invite" | "register" (ADR-044)
  const [signupEnabled, setSignupEnabled] = useState(false);

  // Holds the just-logged-in session (token + learner + school) while
  // must_change_password is true, so the form below can complete the
  // login with a new password instead of asking the student to log in
  // a second time right after setting one.
  const [pendingSession, setPendingSession] = useState(null);
  const [newPassword, setNewPassword] = useState("");
  const [newPasswordConfirm, setNewPasswordConfirm] = useState("");
  const [changing, setChanging] = useState(false);
  const [changeError, setChangeError] = useState(null);

  // ADR-044: the cellphone sign-up link follows the chosen school's setting
  useEffect(() => {
    if (!schoolId) return;
    let cancelled = false;
    fetchSignupAvailable(schoolId)
      .then((r) => !cancelled && setSignupEnabled(!!r.enabled))
      .catch(() => !cancelled && setSignupEnabled(false));
    return () => {
      cancelled = true;
    };
  }, [schoolId]);

  useEffect(() => {
    (async () => {
      try {
        const fetchedSchools = await fetchSchools();
        setSchools(fetchedSchools);
        if (fetchedSchools.length > 0) setSchoolId(fetchedSchools[0].id);
        else
          setLoadError(
            "No schools are set up yet. Run backend/scripts/seed_dev_data.py, or ask THUTOra to add one.",
          );
      } catch (err) {
        setLoadError(
          `Could not reach the backend at http://localhost:8000 (${err.message}). Is uvicorn running?`,
        );
      }
    })();
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!schoolId || !studentNumber.trim() || !password || loading) return;
    setLoading(true);
    setError(null);
    try {
      const response = await login({
        schoolId,
        studentNumber: studentNumber.trim(),
        password,
      });
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
    if (newPassword.length > 72) {
      setChangeError("Choose a password of at most 72 characters.");
      return;
    }
    if (newPassword !== newPasswordConfirm) {
      setChangeError("Those two passwords don't match.");
      return;
    }
    setChanging(true);
    setChangeError(null);
    try {
      const changed = await changePassword({
        token: pendingSession.access_token,
        currentPassword: password,
        newPassword,
      });
      // Code review #6: changing the password ends older tokens, so the
      // backend returns a fresh one for this session.
      onLogin({
        ...pendingSession,
        access_token: changed.access_token || pendingSession.access_token,
        must_change_password: false,
      });
    } catch (err) {
      setChangeError(err.message);
    } finally {
      setChanging(false);
    }
  };

  const brand = (
    <div className="login-screen__brand">
      {/* ADR-040: one login for every product, so all four marks */}
      <Wordmark product="learn" showProduct={false} size="lg" />
      <div className="login-screen__products" aria-hidden="true">
        {["learn", "teach", "connect", "admin", "insights"].map((p) => (
          <img
            key={p}
            src={`/thutora-${p}-logo.png`}
            alt=""
            title={p.toUpperCase()}
          />
        ))}
      </div>
    </div>
  );

  if (pendingSession) {
    return (
      <div className="login-screen">
        <div className="login-screen__card">
          {brand}
          <h1 className="login-screen__title">Choose a new password</h1>
          <p className="login-screen__subtitle">
            You logged in with a temporary password — set your own before
            continuing.
          </p>
          <form
            className="login-screen__form"
            onSubmit={handleChangePassword}
            autoComplete="on"
          >
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
            {changeError && (
              <div className="login-screen__error">{changeError}</div>
            )}
            <button type="submit" disabled={changing}>
              {changing ? "Saving…" : "Set password and continue"}
            </button>
          </form>
        </div>
      </div>
    );
  }

  if (familyMode) {
    return (
      <div className="login-screen">
        <div className="login-screen__card">
          {brand}
          {familyMode === "register" ? (
            <RegisterSchool onBack={() => setFamilyMode(null)} />
          ) : (
            <ParentSignup
              mode={familyMode}
              schools={schools}
              schoolId={schoolId}
              setSchoolId={setSchoolId}
              onLogin={onLogin}
              onBack={() => setFamilyMode(null)}
            />
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="login-screen">
      <div className="login-screen__card">
        {brand}
        <h1 className="login-screen__title">Log in</h1>
        {notice && <div className="login-screen__notice">{notice}</div>}
        {loadError && <div className="login-screen__error">{loadError}</div>}
        <form
          className="login-screen__form"
          onSubmit={handleSubmit}
          autoComplete="on"
        >
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
            {/* NEW 15 Nov 2026 (ADR-024): the backend's User.student_number
                column is reused as a generic login identifier for a
                teacher's staff number too (see provision_teacher()'s
                docstring) -- this label covers both without the login
                form itself needing to know which role is signing in. */}
            <span>Student, staff or parent number</span>
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
        <div className="login-screen__family">
          {signupEnabled && (
            <button
              type="button"
              className="privacy-link"
              onClick={() => setFamilyMode("signup")}
            >
              Parent? Sign up with your cellphone
            </button>
          )}
          <button
            type="button"
            className="privacy-link"
            onClick={() => setFamilyMode("invite")}
          >
            Have an invite code?
          </button>
        </div>
        <div className="login-screen__family">
          <button
            type="button"
            className="privacy-link"
            onClick={() => setFamilyMode("register")}
          >
            New to THUTOra? Register your school
          </button>
          <button
            type="button"
            className="privacy-link"
            onClick={() => setShowPrivacy(true)}
          >
            Privacy notice
          </button>
        </div>
      </div>
      {showPrivacy && <PrivacyNotice onClose={() => setShowPrivacy(false)} />}
    </div>
  );
}
