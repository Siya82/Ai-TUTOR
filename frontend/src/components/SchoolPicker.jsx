/*
 * NEW 19 Nov 2026 (code review 19 Nov #12). Find your school by typing part
 * of its name (or its EMIS number) instead of scrolling one long list --
 * a national roll-out means thousands of schools. The school chosen last
 * time on this device is remembered, so most people never need to search.
 */
import { useEffect, useRef, useState } from "react";
import { searchSchools } from "../api";

export default function SchoolPicker({ value, onChange, label = "School", disabled = false, autoFocus = false }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [open, setOpen] = useState(!value);
  const [error, setError] = useState(null);
  const timer = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    clearTimeout(timer.current);
    timer.current = setTimeout(async () => {
      try {
        setResults(await searchSchools(query.trim()));
        setError(null);
      } catch (err) {
        setError(err.message);
      }
    }, query ? 250 : 0);
    return () => clearTimeout(timer.current);
  }, [query, open]);

  if (value && !open) {
    return (
      <div className="login-screen__field">
        <span>{label}</span>
        <div className="school-picker__chosen">
          <strong>{value.name}</strong>
          {!disabled && (
            <button type="button" className="admin-screen__link-button" onClick={() => setOpen(true)}>
              Change
            </button>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="login-screen__field school-picker">
      <label htmlFor="school-search">{label}</label>
      <input
        id="school-search"
        type="search"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Type your school's name"
        autoComplete="off"
        autoFocus={autoFocus}
        disabled={disabled}
      />
      {error && <div className="login-screen__error">{error}</div>}
      <ul className="school-picker__results" role="listbox" aria-label="Schools">
        {results.map((s) => (
          <li key={s.id}>
            <button
              type="button"
              role="option"
              aria-selected={value?.id === s.id}
              onClick={() => {
                onChange({ id: s.id, name: s.name });
                setOpen(false);
                setQuery("");
              }}
            >
              {s.name}
              {s.kind === "office" && <span className="school-picker__kind"> · education office</span>}
              {s.province && s.kind !== "office" && <span className="school-picker__kind"> · {s.province}</span>}
            </button>
          </li>
        ))}
        {query.trim() && results.length === 0 && !error && (
          <li className="admin-screen__muted">No school matches “{query.trim()}”.</li>
        )}
      </ul>
      {value && (
        <button type="button" className="admin-screen__link-button" onClick={() => setOpen(false)}>
          Keep {value.name}
        </button>
      )}
    </div>
  );
}
