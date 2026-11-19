/*
 * NEW 19 Nov 2026 (ADR-043). Two ways a family member gets a CONNECT login
 * without the school handing one out:
 *  - "signup": a parent enters their cellphone; if it matches a guardian
 *    contact the school holds for an enrolled learner, an SMS code is sent.
 *    The code proves they own that number; the school's record proves the
 *    number belongs to the learner's parent/guardian.
 *  - "invite": a viewer (e.g. a grandparent) redeems a code a guardian made.
 * Both end by logging in normally, so the session looks like any other.
 */
import { useState } from "react";
import SchoolPicker from "./SchoolPicker";
import { login, redeemViewerInvite, startParentSignup, verifyParentSignup } from "../api";

function PasswordFields({ password, setPassword, confirm, setConfirm }) {
  return (
    <>
      <label className="login-screen__field">
        <span>Choose a password</span>
        <input
          type="password"
          autoComplete="new-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          minLength={8}
          maxLength={72}
          required
        />
      </label>
      <label className="login-screen__field">
        <span>Confirm password</span>
        <input
          type="password"
          autoComplete="new-password"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          minLength={8}
          maxLength={72}
          required
        />
      </label>
    </>
  );
}

export default function ParentSignup({ mode, school, setSchool, onLogin, onBack }) {
  const schoolId = school?.id || "";
  const [step, setStep] = useState("phone");
  const [cellphone, setCellphone] = useState("");
  const [code, setCode] = useState("");
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [message, setMessage] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(null);

  const run = async (fn) => {
    setBusy(true);
    setError(null);
    try {
      await fn();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const checkPasswords = () => {
    if (password.length < 8) throw new Error("Choose a password at least 8 characters long.");
    if (password !== confirm) throw new Error("Those two passwords don't match.");
  };

  const finish = (loginNumber) => {
    setDone({ loginNumber });
  };

  const continueIn = () =>
    run(async () => {
      onLogin(await login({ schoolId, studentNumber: done.loginNumber, password }));
    });

  const schoolSelect = (
    <SchoolPicker value={school} onChange={setSchool} label="Your child's school" disabled={step !== "phone"} />
  );

  if (done) {
    return (
      <>
        <h1 className="login-screen__title">You're signed up</h1>
        <p className="login-screen__subtitle">
          Your login number is <strong>{done.loginNumber}</strong>. Use it with your password next time.
        </p>
        {error && <div className="login-screen__error">{error}</div>}
        <button type="button" onClick={continueIn} disabled={busy}>
          Continue
        </button>
      </>
    );
  }

  if (mode === "invite") {
    return (
      <>
        <h1 className="login-screen__title">Use an invite code</h1>
        <p className="login-screen__subtitle">A parent or guardian gave you a code to see their child's progress.</p>
        <form
          className="login-screen__form"
          onSubmit={(e) => {
            e.preventDefault();
            run(async () => {
              checkPasswords();
              const r = await redeemViewerInvite({ schoolId, code: code.trim(), password });
              finish(r.login_number);
            });
          }}
        >
          {schoolSelect}
          <label className="login-screen__field">
            <span>Invite code</span>
            <input value={code} onChange={(e) => setCode(e.target.value)} placeholder="ABCD-1234" required />
          </label>
          <PasswordFields {...{ password, setPassword, confirm, setConfirm }} />
          {error && <div className="login-screen__error">{error}</div>}
          <button type="submit" disabled={busy || !school}>
            {busy ? "Checking…" : "Create my login"}
          </button>
        </form>
        <button type="button" className="privacy-link" onClick={onBack}>
          Back to log in
        </button>
      </>
    );
  }

  return (
    <>
      <h1 className="login-screen__title">Parent sign-up</h1>
      <p className="login-screen__subtitle">
        Use the cellphone number you gave your child's school. We'll SMS you a code.
      </p>
      {step === "phone" ? (
        <form
          className="login-screen__form"
          onSubmit={(e) => {
            e.preventDefault();
            run(async () => {
              const r = await startParentSignup(schoolId, cellphone.trim());
              setMessage(r.message);
              setStep("code");
            });
          }}
        >
          {schoolSelect}
          <label className="login-screen__field">
            <span>Cellphone number</span>
            <input
              type="tel"
              autoComplete="tel"
              value={cellphone}
              onChange={(e) => setCellphone(e.target.value)}
              placeholder="082 123 4567"
              required
              autoFocus
            />
          </label>
          {error && <div className="login-screen__error">{error}</div>}
          <button type="submit" disabled={busy || !school}>
            {busy ? "Sending…" : "Send me a code"}
          </button>
        </form>
      ) : (
        <form
          className="login-screen__form"
          onSubmit={(e) => {
            e.preventDefault();
            run(async () => {
              checkPasswords();
              const r = await verifyParentSignup({ schoolId, cellphone, code: code.trim(), password, fullName });
              finish(r.login_number);
            });
          }}
        >
          {message && <div className="login-screen__notice">{message}</div>}
          <label className="login-screen__field">
            <span>6-digit code</span>
            <input
              inputMode="numeric"
              autoComplete="one-time-code"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              maxLength={6}
              required
              autoFocus
            />
          </label>
          <label className="login-screen__field">
            <span>Your name</span>
            <input value={fullName} onChange={(e) => setFullName(e.target.value)} maxLength={100} />
          </label>
          <PasswordFields {...{ password, setPassword, confirm, setConfirm }} />
          {error && <div className="login-screen__error">{error}</div>}
          <button type="submit" disabled={busy}>
            {busy ? "Checking…" : "Verify and sign up"}
          </button>
          <button type="button" className="admin-screen__link-button" onClick={() => setStep("phone")}>
            Use a different number
          </button>
        </form>
      )}
      <button type="button" className="privacy-link" onClick={onBack}>
        Back to log in
      </button>
    </>
  );
}
