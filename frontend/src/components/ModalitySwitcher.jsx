/*
 * Toggle between Text and Audio.
 *
 * UPDATED 8 Nov 2026: originally built with all four REBUILD_SPEC.md
 * modalities (Text, Audio, Animated, Visual). After live testing, Siya
 * found that Animated (step-reveal) and Visual (number-line) weren't
 * adding anything distinct over Audio -- the content was the same
 * either way, just presented with extra motion/graphics that didn't
 * serve a different need. Narrowed to Text + Audio, with pause/resume
 * added to Audio (see ChatScreen.jsx) so a learner who wants to read
 * instead of listen can pause rather than only stop outright. The
 * StepReveal/NumberLineSVG components and the framer-motion dependency
 * they needed were removed, not just hidden -- see BUILD_LOG.md.
 */

const MODALITIES = [
  { id: "text", label: "Text" },
  { id: "audio", label: "Audio" },
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
