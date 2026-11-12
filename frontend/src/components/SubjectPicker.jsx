/*
 * Subject picker. NEW 12 Nov 2026, multi-subject support (ADR-013) --
 * didn't exist before because there was only ever one seeded subject
 * (Pure Mathematics). Mirrors TopicPicker.jsx's shape; ChatScreen.jsx
 * filters the topic list to the selected subject before handing it to
 * TopicPicker.
 */

export default function SubjectPicker({ subjects, selectedSubjectId, onChange, disabled }) {
  return (
    <label className="subject-picker">
      <span className="subject-picker__label">Subject</span>
      <select
        value={selectedSubjectId || ""}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled || subjects.length === 0}
      >
        {subjects.map((s) => (
          <option key={s.id} value={s.id}>
            {s.name}
          </option>
        ))}
      </select>
    </label>
  );
}
