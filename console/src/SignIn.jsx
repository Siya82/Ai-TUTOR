/*
 * ADR-051: three steps -- email and password; the authenticator code (set up
 * with a QR code the first time); a new password if this is a temporary one.
 */
import { useEffect, useState } from "react";
import QRCode from "qrcode";
import { KeyRound, ShieldCheck, Smartphone } from "lucide-react";
import { call } from "./api";

function Brand() {
  return (
    <div className="brand brand--center">
      <img src="/thutora-core-logo.png" alt="" className="brand__mark" />
      <span className="brand__name">
        THUTO<span className="brand__ra">ra</span>
      </span>
      <span className="brand__badge">CONSOLE</span>
    </div>
  );
}

function Qr({ uri }) {
  const [src, setSrc] = useState(null);
  useEffect(() => {
    QRCode.toDataURL(uri, { margin: 1, width: 200 }).then(setSrc, () => setSrc(null));
  }, [uri]);
  return src ? <img src={src} alt="QR code to add THUTOra Console to your authenticator app" className="qr" /> : null;
}

export default function SignIn({ session, onSignedIn, notice }) {
  const [step, setStep] = useState(session?.me?.must_change_password ? "password" : "login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [mfa, setMfa] = useState(null); // {token, step, secret?, otpauth_uri?}
  const [code, setCode] = useState("");
  const [full, setFull] = useState(session);
  const [newPw, setNewPw] = useState("");
  const [newPw2, setNewPw2] = useState("");
  const [error, setError] = useState(null);
  // after a reload we no longer hold the temporary password, so ask for it
  const [askCurrent] = useState(Boolean(session?.me?.must_change_password));
  const [busy, setBusy] = useState(false);

  const run = async (fn) => {
    setBusy(true);
    setError(null);
    try {
      await fn();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const submitLogin = (e) => {
    e.preventDefault();
    run(async () => {
      const r = await call("/auth/login", { method: "POST", body: { email, password } });
      setMfa(r);
      setCode("");
      setStep("code");
    });
  };

  const submitCode = (e) => {
    e.preventDefault();
    run(async () => {
      const r = await call("/auth/verify", { method: "POST", token: mfa.token, body: { code: code.replace(/\s/g, "") } });
      const s = { token: r.token, me: r.me };
      if (r.me.must_change_password) {
        setFull(s);
        setStep("password");
      } else {
        onSignedIn(s);
      }
    });
  };

  const submitPassword = (e) => {
    e.preventDefault();
    if (newPw !== newPw2) {
      setError("The two new passwords don't match.");
      return;
    }
    run(async () => {
      const r = await call("/auth/change-password", {
        method: "POST",
        token: full.token,
        body: { current_password: password, new_password: newPw },
      });
      onSignedIn({ token: r.token, me: r.me });
    });
  };

  return (
    <div className="signin">
      <div className="signin__card">
        <Brand />
        <p className="signin__note">For Zynora staff only. Schools get help from the Help button in their app.</p>
        {notice && <p className="banner banner--info" role="status">{notice}</p>}
        {error && <p className="banner banner--error" role="alert">{error}</p>}

        {step === "login" && (
          <form onSubmit={submitLogin} className="form">
            <label>
              Work email
              <input type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} required />
            </label>
            <label>
              Password
              <input type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required />
            </label>
            <button className="btn btn--primary" disabled={busy}>
              <KeyRound size={16} aria-hidden="true" /> Continue
            </button>
          </form>
        )}

        {step === "code" && mfa && (
          <form onSubmit={submitCode} className="form">
            {mfa.step === "setup" ? (
              <div className="setup">
                <h2>
                  <Smartphone size={18} aria-hidden="true" /> Set up your authenticator app
                </h2>
                <ol>
                  <li>Open Google Authenticator or Microsoft Authenticator on your phone.</li>
                  <li>Add an account and scan this code.</li>
                  <li>Type the 6-digit code it shows.</li>
                </ol>
                <Qr uri={mfa.otpauth_uri} />
                <p className="muted">
                  Can't scan? Enter this key instead: <code className="key">{mfa.secret.match(/.{1,4}/g).join(" ")}</code>
                </p>
              </div>
            ) : (
              <p>Open your authenticator app and type the 6-digit code for THUTOra Console.</p>
            )}
            <label>
              6-digit code
              <input
                inputMode="numeric"
                autoComplete="one-time-code"
                pattern="[0-9 ]{6,8}"
                maxLength={8}
                value={code}
                onChange={(e) => setCode(e.target.value)}
                required
                autoFocus
              />
            </label>
            <button className="btn btn--primary" disabled={busy}>
              <ShieldCheck size={16} aria-hidden="true" /> Sign in
            </button>
            <button type="button" className="btn btn--ghost" onClick={() => setStep("login")}>
              Back
            </button>
          </form>
        )}

        {step === "password" && (
          <form onSubmit={submitPassword} className="form">
            <h2>Choose your own password</h2>
            <p className="muted">At least 12 characters. A short sentence is easy to remember and hard to guess.</p>
            {askCurrent && (
              <label>
                Temporary password
                <input type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required />
              </label>
            )}
            <label>
              New password
              <input type="password" autoComplete="new-password" minLength={12} maxLength={72} value={newPw} onChange={(e) => setNewPw(e.target.value)} required />
            </label>
            <label>
              New password again
              <input type="password" autoComplete="new-password" minLength={12} maxLength={72} value={newPw2} onChange={(e) => setNewPw2(e.target.value)} required />
            </label>
            <button className="btn btn--primary" disabled={busy}>
              Save and continue
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
