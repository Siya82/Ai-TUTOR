/*
 * Subject picker. NEW 12 Nov 2026, multi-subject support (ADR-013) --
 * didn't exist before because there was only ever one seeded subject
 * (Pure Mathematics). Mirrors TopicPicker.jsx's shape; ChatScreen.jsx
 * filters the topic list to the selected subject before handing it to
 * TopicPicker.
 *
 * UPDATED 13 Nov 2026 (Grade 11 added, ADR-014): two subjects can now
 * share a name ("Pure Mathematics" grade 10 and grade 11) -- the grade
 * is now shown in every option's label so they're never ambiguous in
 * the dropdown, not just for the one subject that happens to have a
 * sibling today.
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
            {s.name} (Grade {s.grade})
          </option>
        ))}
      </select>
    </label>
  );
}
