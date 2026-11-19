/*
 * NEW 19 Nov 2026 (code review 19 Nov #9). "Change password" for everyone --
 * learners, staff, parents and officials -- from their own header. Changing
 * it signs out every OTHER device (token_version); this one carries on with
 * the fresh token the server returns.
 */
import { useState } from "react";
import { KeyRound } from "lucide-react";
import { changePassword, replaceToken } from "../api";
import { ICON_BUTTON } from "./icons";

export default function ChangePassword({ token }) {
  const [open, setOpen] = useState(false);
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState(null);
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);

  const close = () => {
    setOpen(false);
    setCurrent("");
    setNext("");
    setConfirm("");
    setError(null);
    setDone(false);
  };

  const submit = async (e) => {
    e.preventDefault();
    if (next.length < 8) return setError("Choose a password at least 8 characters long.");
    if (next !== confirm) return setError("Those two passwords don't match.");
    setBusy(true);
    setError(null);
    try {
      const result = await changePassword({ token, currentPassword: current, newPassword: next });
      replaceToken(token, result.access_token);
      setDone(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <button type="button" className="chat-screen__logout" onClick={() => setOpen(true)} title="Change password">
        <KeyRound size={ICON_BUTTON} aria-hidden="true" />
        <span className="change-password__label">Password</span>
      </button>
      {open && (
        <div className="modal-backdrop" role="dialog" aria-modal="true" aria-label="Change password" onClick={close}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <h2 className="login-screen__title">Change password</h2>
            {done ? (
              <>
                <p className="login-screen__subtitle">
                  Done. Use your new password next time. Any other device you were logged in on has been logged out.
                </p>
                <button type="button" onClick={close}>
                  Close
                </button>
              </>
            ) : (
              <form className="login-screen__form" onSubmit={submit}>
                <label className="login-screen__field">
                  <span>Current password</span>
                  <input
                    type="password"
                    autoComplete="current-password"
                    value={current}
                    onChange={(e) => setCurrent(e.target.value)}
                    required
                    autoFocus
                  />
                </label>
                <label className="login-screen__field">
                  <span>New password</span>
                  <input
                    type="password"
                    autoComplete="new-password"
                    value={next}
                    onChange={(e) => setNext(e.target.value)}
                    minLength={8}
                    maxLength={72}
                    required
                  />
                </label>
                <label className="login-screen__field">
                  <span>Confirm new password</span>
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
                {error && <div className="login-screen__error">{error}</div>}
                <button type="submit" disabled={busy}>
                  {busy ? "Saving…" : "Change password"}
                </button>
                <button type="button" className="privacy-link" onClick={close}>
                  Cancel
                </button>
              </form>
            )}
          </div>
        </div>
      )}
    </>
  );
}
