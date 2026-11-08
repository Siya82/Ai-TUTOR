/*
 * Topic picker. REBUILD_SPEC.md Section 3 explicitly flagged that the
 * recovered api.js only exposed a handful of topics in the UI "even
 * though more were seeded in the backend" and said to "re-check this
 * against the full 12-topic list on rebuild" -- this fetches every
 * topic from GET /topics (added this step) rather than hardcoding a
 * subset.
 */

export default function TopicPicker({ topics, selectedTopicId, onChange, disabled }) {
  return (
    <label className="topic-picker">
      <span className="topic-picker__label">Topic</span>
      <select
        value={selectedTopicId || ""}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled || topics.length === 0}
      >
        {topics.map((t) => (
          <option key={t.id} value={t.id}>
            {t.name}
          </option>
        ))}
      </select>
    </label>
  );
}
