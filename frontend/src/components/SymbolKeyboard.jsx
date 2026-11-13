/*
 * On-screen symbol keyboard for the message composer.
 *
 * NEW 8 Nov 2026, step 7 follow-up -- not in REBUILD_SPEC.md at all;
 * a genuinely new feature, added after live testing surfaced that a
 * standard keyboard has no sin/cos/tan, θ, √, π, ≤/≥, etc., and that
 * different CAPS topics need different symbols (a learner solving a
 * Trigonometry question needs sin/cos/tan/θ/°; one solving Measurement
 * needs π and √; etc.).
 *
 * TOPIC_SYMBOLS is keyed by the exact topic names seed_dev_data.py
 * creates. A topic name that doesn't match anything (e.g. if the seed
 * data changes) falls back to COMMON_SYMBOLS only, rather than showing
 * nothing or throwing.
 *
 * FIX 12 Nov 2026 (multi-subject support, ADR-013): added entries for
 * the Physical Sciences (Physics strand) topics -- different symbol
 * needs again (Ω, Δ, vector arrows, °) from either Maths bucket above.
 *
 * FIX 13 Nov 2026 (Grade 11 added, ADR-014): TOPIC_SYMBOLS is keyed by
 * topic NAME, not id -- a Grade 11 topic that shares its exact name
 * with a Grade 10 one (Vectors in Two Dimensions, Electrostatics,
 * Electric Circuits) automatically reuses that entry, which is
 * correct here since the symbol needs really are the same. Only the
 * three genuinely NEW Grade 11 topic names (no Grade 10 namesake) --
 * Newton's Laws, Newton's Universal Law of Gravitation,
 * Electromagnetism -- needed their own new entries below.
 */

const COMMON_SYMBOLS = [
  { label: "(", insert: "(" },
  { label: ")", insert: ")" },
  { label: "²", insert: "²" },
  { label: "√", insert: "√(" },
  { label: "=", insert: "=" },
];

const TOPIC_SYMBOLS = {
  "Algebraic Expressions": [
    { label: "x", insert: "x" },
    { label: "y", insert: "y" },
    { label: "³", insert: "³" },
  ],
  Exponents: [
    { label: "x", insert: "x" },
    { label: "³", insert: "³" },
    { label: "ⁿ", insert: "ⁿ" },
  ],
  "Equations and Inequalities": [
    { label: "x", insert: "x" },
    { label: "≤", insert: "≤" },
    { label: "≥", insert: "≥" },
    { label: "≠", insert: "≠" },
  ],
  "Number Patterns": [
    { label: "n", insert: "n" },
    { label: "Σ", insert: "Σ" },
    { label: "Tₙ", insert: "Tₙ" },
  ],
  Trigonometry: [
    { label: "sin", insert: "sin(" },
    { label: "cos", insert: "cos(" },
    { label: "tan", insert: "tan(" },
    { label: "θ", insert: "θ" },
    { label: "°", insert: "°" },
  ],
  Functions: [
    { label: "f(x)", insert: "f(x)" },
    { label: "x", insert: "x" },
    { label: "y", insert: "y" },
  ],
  "Finance, Growth and Decay": [
    { label: "%", insert: "%" },
    { label: "R", insert: "R" },
    { label: "ⁿ", insert: "ⁿ" },
  ],
  "Analytical Geometry": [
    { label: "x", insert: "x" },
    { label: "y", insert: "y" },
    { label: "³", insert: "³" },
  ],
  "Euclidean Geometry": [
    { label: "°", insert: "°" },
    { label: "Δ", insert: "Δ" },
    { label: "≅", insert: "≅" },
    { label: "∠", insert: "∠" },
    { label: "∥", insert: "∥" },
  ],
  Measurement: [
    { label: "π", insert: "π" },
    { label: "³", insert: "³" },
  ],
  Statistics: [
    { label: "x̄", insert: "x̄" },
    { label: "Σ", insert: "Σ" },
    { label: "%", insert: "%" },
  ],
  Probability: [
    { label: "%", insert: "%" },
    { label: "∩", insert: "∩" },
    { label: "∪", insert: "∪" },
  ],
  "Vectors in Two Dimensions": [
    { label: "→", insert: "→" },
    { label: "°", insert: "°" },
    { label: "θ", insert: "θ" },
  ],
  "Motion in One Dimension": [
    { label: "Δ", insert: "Δ" },
    { label: "m/s", insert: "m/s" },
    { label: "m/s²", insert: "m/s²" },
  ],
  "Mechanical Energy": [
    { label: "Δ", insert: "Δ" },
    { label: "J", insert: "J" },
  ],
  "Waves, Sound and Light": [
    { label: "λ", insert: "λ" },
    { label: "Hz", insert: "Hz" },
  ],
  "Electromagnetic Radiation": [
    { label: "λ", insert: "λ" },
    { label: "Hz", insert: "Hz" },
  ],
  Magnetism: [
    { label: "N", insert: "N" },
    { label: "S", insert: "S" },
  ],
  Electrostatics: [
    { label: "C", insert: "C" },
    { label: "⁻", insert: "⁻" },
    { label: "⁺", insert: "⁺" },
  ],
  "Electric Circuits": [
    { label: "Ω", insert: "Ω" },
    { label: "V", insert: "V" },
    { label: "A", insert: "A" },
  ],
  "Newton's Laws": [
    { label: "N", insert: "N" },
    { label: "μ", insert: "μ" },
    { label: "→", insert: "→" },
  ],
  "Newton's Universal Law of Gravitation": [
    { label: "G", insert: "G" },
    { label: "×", insert: "×" },
    { label: "⁻", insert: "⁻" },
  ],
  Electromagnetism: [
    { label: "Φ", insert: "Φ" },
    { label: "Δ", insert: "Δ" },
    { label: "ε", insert: "ε" },
  ],
};

export default function SymbolKeyboard({ topicName, onInsert }) {
  const topicButtons = TOPIC_SYMBOLS[topicName] || [];

  return (
    <div className="symbol-keyboard" role="toolbar" aria-label="Math symbol keyboard">
      {topicButtons.map((sym) => (
        <button key={sym.label} type="button" onClick={() => onInsert(sym.insert)}>
          {sym.label}
        </button>
      ))}
      {topicButtons.length > 0 && <span className="symbol-keyboard__divider" aria-hidden="true" />}
      {COMMON_SYMBOLS.map((sym) => (
        <button key={sym.label} type="button" onClick={() => onInsert(sym.insert)}>
          {sym.label}
        </button>
      ))}
    </div>
  );
}
