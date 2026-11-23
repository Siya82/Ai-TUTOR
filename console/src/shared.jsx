// Small shared pieces for the Console screens.
import { useState } from "react";
import { Copy } from "lucide-react";

export function Banner({ kind = "error", children }) {
  if (!children) return null;
  return (
    <p className={`banner banner--${kind}`} role={kind === "error" ? "alert" : "status"}>
      {children}
    </p>
  );
}

// A new login's one-time password: shown once, with a copy button.
export function OneTimeCredentials({ cred, onDone }) {
  const [copied, setCopied] = useState(false);
  if (!cred) return null;
  const text = `${cred.name}\nLog in at: ${cred.school}\nLogin number: ${cred.login}\nTemporary password: ${cred.temp_password}`;
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  };
  return (
    <div className="credentials" role="status">
      <h3>New login for {cred.name}</h3>
      <dl>
        <dt>Choose on the login screen</dt>
        <dd>{cred.school}</dd>
        <dt>Login number</dt>
        <dd>
          <code>{cred.login}</code>
        </dd>
        <dt>Temporary password</dt>
        <dd>
          <code>{cred.temp_password}</code>
        </dd>
      </dl>
      <p className="muted">
        Shown once. Give it to the person directly (phone, not email). They choose their own password at first login.
      </p>
      <div className="row">
        <button type="button" className="btn" onClick={copy}>
          <Copy size={16} aria-hidden="true" /> {copied ? "Copied" : "Copy"}
        </button>
        {onDone && (
          <button type="button" className="btn btn--ghost" onClick={onDone}>
            Done
          </button>
        )}
      </div>
    </div>
  );
}

export function Chips({ label, value, options, onChange }) {
  return (
    <div className="chips" role="group" aria-label={label}>
      {options.map(([id, text]) => (
        <button
          key={id}
          type="button"
          className={`chip${value === id ? " chip--active" : ""}`}
          aria-pressed={value === id}
          onClick={() => onChange(id)}
        >
          {text}
        </button>
      ))}
    </div>
  );
}
