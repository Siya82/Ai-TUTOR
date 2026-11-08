/*
 * Toggle for the four teaching modalities (REBUILD_SPEC.md Section 3:
 * "whatever UI/toggle exists for switching modality" was never
 * recovered -- this is a genuine rebuild of that control, not a
 * recovery). New messages render using whichever modality is selected
 * at the moment they arrive; switching modality does not retroactively
 * re-render earlier messages in the transcript.
 */

const MODALITIES = [
  { id: "text", label: "Text" },
  { id: "audio", label: "Audio" },
  { id: "animated", label: "Animated" },
  { id: "visual", label: "Visual" },
];

export default function ModalitySwitcher({ modality, onChange }) {
  return (
    <div className="modality-switcher" role="tablist" aria-label="Teaching modality">
      {MODALITIES.map((m) => (
        <button
          key={m.id}
          type="button"
          role="tab"
          aria-selected={modality === m.id}
          className={`modality-switcher__btn ${modality === m.id ? "is-active" : ""}`}
          onClick={() => onChange(m.id)}
        >
          {m.label}
        </button>
      ))}
    </div>
  );
}
