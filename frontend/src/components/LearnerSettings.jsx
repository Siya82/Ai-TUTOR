/*
 * NEW 19 Nov 2026 (ADR-035). A small settings menu in the learner's header:
 *  - "Also explain in": the learner's home language; the tutor keeps
 *    teaching in English but may explain in this language too, always
 *    keeping the English exam terms.
 *  - "Save data": textbook figures load only when tapped (this device only).
 */
import { useEffect, useRef, useState } from "react";
import { Settings } from "lucide-react";
import { fetchHomeLanguages, setHomeLanguage } from "../api";
import { isLowData, setLowData } from "../utils/lowData";
import { ICON_BUTTON } from "./icons";
import PrivacyNotice from "./PrivacyNotice";

export default function LearnerSettings({ token, learner, onLearnerChange }) {
  const [open, setOpen] = useState(false);
  const [languages, setLanguages] = useState([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [lowData, setLowDataState] = useState(isLowData);
  const [showPrivacy, setShowPrivacy] = useState(false);
  const boxRef = useRef(null);

  useEffect(() => {
    if (!open || languages.length) return undefined;
    let cancelled = false;
    fetchHomeLanguages()
      .then((list) => {
        if (!cancelled) setLanguages(list);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [open, languages.length]);

  useEffect(() => {
    if (!open) return undefined;
    const close = (e) => {
      if (boxRef.current && !boxRef.current.contains(e.target)) setOpen(false);
    };
    const onKey = (e) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const changeLanguage = async (value) => {
    setSaving(true);
    setError(null);
    try {
      const profile = await setHomeLanguage(token, value || null);
      onLearnerChange(profile);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="learner-settings" ref={boxRef}>
      <button
        type="button"
        className="chat-screen__logout"
        aria-expanded={open}
        aria-haspopup="dialog"
        onClick={() => setOpen((o) => !o)}
      >
        <Settings size={ICON_BUTTON} aria-hidden="true" />
        Settings
      </button>
      {open && (
        <div className="learner-settings__panel" role="dialog" aria-label="Settings">
          <label className="admin-form__field">
            <span>Also explain in</span>
            <select
              value={learner.home_language || "English"}
              onChange={(e) => changeLanguage(e.target.value)}
              disabled={saving || languages.length === 0}
            >
              {(languages.length ? languages : ["English"]).map((l) => (
                <option key={l} value={l}>
                  {l === "English" ? "English only" : l}
                </option>
              ))}
            </select>
          </label>
          <p className="admin-screen__muted">
            THUTOra teaches in English, like your exams. Pick your home language and it can also explain
            in that language when you're stuck — ask it in your language any time.
          </p>
          <label className="admin-form__checkbox-row">
            <input
              type="checkbox"
              checked={lowData}
              onChange={(e) => {
                setLowData(e.target.checked);
                setLowDataState(e.target.checked);
              }}
            />
            Save data (textbook pictures load only when you tap them)
          </label>
          {error && <div className="admin-screen__error">{error}</div>}
          <button type="button" className="privacy-link" onClick={() => setShowPrivacy(true)}>
            Privacy notice
          </button>
        </div>
      )}
      {showPrivacy && <PrivacyNotice onClose={() => setShowPrivacy(false)} />}
    </div>
  );
}
