/*
 * NEW 19 Nov 2026 (ADR-044). The school's profile (name, EMIS number,
 * province, quintile, contact details) and settings that change how
 * THUTOra behaves for this school. Staff who can't manage the school see
 * it read-only.
 */
import { useEffect, useState } from "react";
import { fetchAiUsage, fetchSchoolProfile, saveSchoolProfile } from "../api";

const FIELDS = ["name", "emis_number", "province", "quintile", "phone", "email", "physical_address"];

export default function SchoolSettings({ token, onRenamed }) {
  const [profile, setProfile] = useState(null);
  const [form, setForm] = useState(null);
  const [error, setError] = useState(null);
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);
  const [usage, setUsage] = useState(null); // deep scan H5

  useEffect(() => {
    let cancelled = false;
    fetchSchoolProfile(token)
      .then((p) => {
        if (cancelled) return;
        setProfile(p);
        setForm(p);
      })
      .catch((err) => !cancelled && setError(err.message));
    fetchAiUsage(token)
      .then((u) => !cancelled && setUsage(u))
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [token]);

  if (error && !form) return <div className="admin-screen__error">{error}</div>;
  if (!form) return <p className="admin-screen__muted">Loading…</p>;
  const ro = !profile.can_edit;
  const set = (k) => (e) => {
    setSaved(false);
    setForm({ ...form, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value });
  };

  const save = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const body = Object.fromEntries(FIELDS.map((k) => [k, form[k] === "" ? null : form[k]]));
      body.quintile = form.quintile ? Number(form.quintile) : null;
      body.parent_signup_enabled = form.parent_signup_enabled;
      body.viewer_invites_enabled = form.viewer_invites_enabled;
      body.require_consent = !!form.require_consent;
      body.ai_budget_usd_month =
        form.ai_budget_usd_month === "" || form.ai_budget_usd_month == null ? null : Number(form.ai_budget_usd_month);
      const p = await saveSchoolProfile(token, body);
      setProfile(p);
      setForm(p);
      setSaved(true);
      onRenamed?.(p.name);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className="school-settings" onSubmit={save}>
      <section className="today-card">
        <h3 className="today-card__title">School profile</h3>
        <div className="school-settings__grid">
          <label className="admin-form__field school-settings__wide">
            <span>School name</span>
            <input value={form.name || ""} onChange={set("name")} maxLength={200} required disabled={ro} />
          </label>
          <label className="admin-form__field">
            <span>EMIS number</span>
            <input
              value={form.emis_number || ""}
              onChange={set("emis_number")}
              inputMode="numeric"
              maxLength={20}
              disabled={ro}
            />
          </label>
          <label className="admin-form__field">
            <span>Province</span>
            <select value={form.province || ""} onChange={set("province")} disabled={ro}>
              <option value="">—</option>
              {profile.provinces.map((p) => (
                <option key={p}>{p}</option>
              ))}
            </select>
          </label>
          <label className="admin-form__field">
            <span>Quintile</span>
            <select value={form.quintile || ""} onChange={set("quintile")} disabled={ro}>
              <option value="">—</option>
              {[1, 2, 3, 4, 5].map((q) => (
                <option key={q} value={q}>
                  Quintile {q}
                </option>
              ))}
            </select>
          </label>
          <label className="admin-form__field">
            <span>Phone</span>
            <input value={form.phone || ""} onChange={set("phone")} maxLength={30} disabled={ro} />
          </label>
          <label className="admin-form__field">
            <span>Email</span>
            <input type="email" value={form.email || ""} onChange={set("email")} maxLength={200} disabled={ro} />
          </label>
          <label className="admin-form__field school-settings__wide">
            <span>Physical address</span>
            <input
              value={form.physical_address || ""}
              onChange={set("physical_address")}
              maxLength={300}
              disabled={ro}
            />
          </label>
        </div>
      </section>
      <section className="today-card">
        <h3 className="today-card__title">Families (CONNECT)</h3>
        <label className="school-settings__toggle">
          <input
            type="checkbox"
            checked={!!form.parent_signup_enabled}
            onChange={set("parent_signup_enabled")}
            disabled={ro}
          />
          <span>
            <strong>Parents can sign themselves up with their cellphone</strong>
            <span className="admin-screen__muted">
              Only numbers on the school's guardian contacts can sign up. Switch off to hand out every parent
              login yourself.
            </span>
          </span>
        </label>
        <label className="school-settings__toggle">
          <input
            type="checkbox"
            checked={!!form.viewer_invites_enabled}
            onChange={set("viewer_invites_enabled")}
            disabled={ro}
          />
          <span>
            <strong>Parents can invite family members to view progress</strong>
            <span className="admin-screen__muted">
              E.g. a grandparent. Viewers see progress only, not notices or tutor conversations.
            </span>
          </span>
        </label>
      </section>
      <section className="today-card">
        <h3 className="today-card__title">Privacy and AI use</h3>
        <label className="school-settings__toggle">
          <input type="checkbox" checked={!!form.require_consent} onChange={set("require_consent")} disabled={ro} />
          <span>
            <strong>Learners need a recorded parent/guardian consent to use the AI tutor</strong>
            <span className="admin-screen__muted">
              Without one, the tutor explains that a consent form is needed, and assignment answers are kept for the
              teacher to mark. Record consent on the Learners tab.
            </span>
          </span>
        </label>
        <div className="school-settings__grid">
          <label className="admin-form__field">
            <span>Monthly AI budget (US$, empty = no limit)</span>
            <input
              type="number"
              min="0"
              step="1"
              value={form.ai_budget_usd_month ?? ""}
              onChange={set("ai_budget_usd_month")}
              disabled={ro}
            />
          </label>
          {usage && (
            <div className="admin-form__field">
              <span>AI use this month</span>
              <strong>
                US${usage.cost_usd.toFixed(2)}
                {usage.budget_usd != null && ` of US$${usage.budget_usd.toFixed(2)}`}
              </strong>
              <span className="admin-screen__muted">
                {Object.entries(usage.by_feature)
                  .map(([f, v]) => `${v.calls} ${f === "tutor" ? "tutor questions" : f}`)
                  .join(" · ") || "No AI use yet this month"}
              </span>
            </div>
          )}
        </div>
      </section>
      {error && <div className="admin-screen__error">{error}</div>}
      {ro ? (
        <p className="admin-screen__muted">Only the principal, deputy principal or school admin can change these.</p>
      ) : (
        <div className="school-settings__actions">
          <button type="submit" disabled={busy}>
            {busy ? "Saving…" : "Save changes"}
          </button>
          {saved && <span className="admin-screen__muted">Saved.</span>}
        </div>
      )}
    </form>
  );
}
