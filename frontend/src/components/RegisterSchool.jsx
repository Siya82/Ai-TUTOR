/*
 * NEW 19 Nov 2026 (ADR-044). "Register your school" -- a request, not an
 * account. THUTOra confirms the school (official number, EMIS) before
 * creating it and the principal's login (scripts/manage_registrations.py).
 */
import { useEffect, useState } from "react";
import { fetchRegistrationOptions, registerSchool } from "../api";

const EMPTY = {
  school_name: "",
  emis_number: "",
  province: "",
  contact_name: "",
  contact_role: "Principal",
  contact_cellphone: "",
  contact_email: "",
  learner_estimate: "",
  message: "",
};

export default function RegisterSchool({ onBack }) {
  const [options, setOptions] = useState({ provinces: [], roles: ["Principal"] });
  const [form, setForm] = useState(EMPTY);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    fetchRegistrationOptions().then(setOptions);
  }, []);

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  if (result) {
    return (
      <>
        <h1 className="login-screen__title">Request received</h1>
        <p className="login-screen__subtitle">{result.message}</p>
        <p className="login-screen__subtitle">
          Your reference: <strong>{result.reference}</strong>
        </p>
        <button type="button" onClick={onBack}>
          Back to log in
        </button>
      </>
    );
  }

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const body = Object.fromEntries(Object.entries(form).map(([k, v]) => [k, v.trim() || null]));
      body.learner_estimate = form.learner_estimate ? Number(form.learner_estimate) : null;
      setResult(await registerSchool(body));
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <h1 className="login-screen__title">Register your school</h1>
      <p className="login-screen__subtitle">
        Tell us about your school. We'll confirm the details with you and set up the principal's login.
      </p>
      <form className="login-screen__form" onSubmit={submit}>
        <label className="login-screen__field">
          <span>School name</span>
          <input value={form.school_name} onChange={set("school_name")} maxLength={200} required autoFocus />
        </label>
        <label className="login-screen__field">
          <span>Province</span>
          <select value={form.province} onChange={set("province")} required>
            <option value="">Choose…</option>
            {options.provinces.map((p) => (
              <option key={p}>{p}</option>
            ))}
          </select>
        </label>
        <label className="login-screen__field">
          <span>EMIS number (if you know it)</span>
          <input value={form.emis_number} onChange={set("emis_number")} inputMode="numeric" maxLength={20} />
        </label>
        <label className="login-screen__field">
          <span>Your name</span>
          <input value={form.contact_name} onChange={set("contact_name")} maxLength={100} required />
        </label>
        <label className="login-screen__field">
          <span>Your role</span>
          <select value={form.contact_role} onChange={set("contact_role")}>
            {options.roles.map((r) => (
              <option key={r}>{r}</option>
            ))}
          </select>
        </label>
        <label className="login-screen__field">
          <span>Cellphone</span>
          <input
            type="tel"
            value={form.contact_cellphone}
            onChange={set("contact_cellphone")}
            placeholder="082 123 4567"
            required
          />
        </label>
        <label className="login-screen__field">
          <span>Email (optional)</span>
          <input type="email" value={form.contact_email} onChange={set("contact_email")} maxLength={200} />
        </label>
        <label className="login-screen__field">
          <span>Roughly how many learners?</span>
          <input type="number" min={1} max={10000} value={form.learner_estimate} onChange={set("learner_estimate")} />
        </label>
        <label className="login-screen__field">
          <span>Anything else (optional)</span>
          <textarea value={form.message} onChange={set("message")} maxLength={2000} rows={3} />
        </label>
        {error && <div className="login-screen__error">{error}</div>}
        <button type="submit" disabled={busy}>
          {busy ? "Sending…" : "Send request"}
        </button>
      </form>
      <button type="button" className="privacy-link" onClick={onBack}>
        Back to log in
      </button>
    </>
  );
}
