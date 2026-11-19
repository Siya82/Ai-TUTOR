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

// UPDATED 19 Nov 2026 (ADR-042): structure keys first. "a/b" inserts an
// empty fraction with the cursor in the top box; "next box" (or Tab) jumps
// to the bottom box. `cursor` = where the caret lands inside the inserted text.
const STRUCTURE_KEYS = [
  { label: "a⁄b", insert: "()/()", cursor: 1, title: "Fraction: type the top, then 'next box' for the bottom" },
  { label: "xⁿ", insert: "^()", cursor: 2, title: "Power" },
  { label: "√", insert: "√()", cursor: 2, title: "Square root" },
  { label: "next ▸", action: "next", title: "Jump to the next box (or press Tab)" },
];

const COMMON_SYMBOLS = [
  { label: "(", insert: "(" },
  { label: ")", insert: ")" },
  { label: "²", insert: "²" },
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
  // NEW 14 Nov 2026 (ADR-018, Accounting added): no trig/Greek-letter
  // needs here, but every Accounting topic deals in Rand amounts and
  // VAT/deduction percentages, neither of which is on a standard
  // keyboard as a single keystroke -- same "small, topic-specific
  // convenience row" idea as the Physics entries above, just for
  // currency instead of units/constants. Shared across every
  // Accounting topic rather than varied per-topic, since the actual
  // need (Rand sign, percent) genuinely doesn't change topic to topic
  // the way it does between, say, Electrostatics and Electromagnetism.
  "Accounting Concepts, GAAP and Internal Control": [
    { label: "R", insert: "R" },
    { label: "%", insert: "%" },
  ],
  "The Accounting Equation": [
    { label: "R", insert: "R" },
    { label: "%", insert: "%" },
  ],
  "Cash Journals (CRJ, CPJ, PCJ)": [
    { label: "R", insert: "R" },
    { label: "%", insert: "%" },
  ],
  "Credit Journals (DJ, DAJ, CJ, CAJ, GJ)": [
    { label: "R", insert: "R" },
    { label: "%", insert: "%" },
  ],
  "General Ledger and Trial Balance": [
    { label: "R", insert: "R" },
    { label: "%", insert: "%" },
  ],
  "Value-Added Tax (VAT)": [
    { label: "R", insert: "R" },
    { label: "%", insert: "%" },
  ],
  "Salaries and Wages": [
    { label: "R", insert: "R" },
    { label: "%", insert: "%" },
  ],
  "Year-End Adjustments": [
    { label: "R", insert: "R" },
    { label: "%", insert: "%" },
  ],
  "Financial Statements (Income Statement and Balance Sheet)": [
    { label: "R", insert: "R" },
    { label: "%", insert: "%" },
  ],
  "Budgeting (Cash Budget)": [
    { label: "R", insert: "R" },
    { label: "%", insert: "%" },
  ],
  // NEW 14 Nov 2026 (ADR-019, Accounting Grade 11 added): same R/%
  // convenience row as the Grade 10 Accounting entries above. Only 9
  // new entries needed, not 11 -- "Budgeting (Cash Budget)" and
  // "Value-Added Tax (VAT)" reuse their exact Grade 10 topic names
  // (ADR-019's cross-grade deepening design), so they already match
  // the two entries above and need nothing added here.
  "Bank Reconciliation": [
    { label: "R", insert: "R" },
    { label: "%", insert: "%" },
  ],
  "Creditors' Reconciliation": [
    { label: "R", insert: "R" },
    { label: "%", insert: "%" },
  ],
  "Fixed Assets": [
    { label: "R", insert: "R" },
    { label: "%", insert: "%" },
  ],
  "Partnerships: Concepts and Formation": [
    { label: "R", insert: "R" },
    { label: "%", insert: "%" },
  ],
  "Partnership Final Accounts and Year-End Adjustments": [
    { label: "R", insert: "R" },
    { label: "%", insert: "%" },
  ],
  "Partnership Financial Statements": [
    { label: "R", insert: "R" },
    { label: "%", insert: "%" },
  ],
  "Analysis and Interpretation of Financial Statements": [
    { label: "R", insert: "R" },
    { label: "%", insert: "%" },
  ],
  "Inventory Systems": [
    { label: "R", insert: "R" },
    { label: "%", insert: "%" },
  ],
  "Manufacturing Cost Accounting": [
    { label: "R", insert: "R" },
    { label: "%", insert: "%" },
  ],
  // NEW 15 Nov 2026 (ADR-022, Pure Mathematics Grade 12 added): most
  // Grade 12 topic names are genuinely new (CAPS introduces distinct
  // sub-skills -- logs, compound angles, calculus notation -- that the
  // existing Grade 10/11 entries don't cover), so each gets its own
  // small, topic-relevant row. "Finance, Growth and Decay",
  // "Analytical Geometry", and "Euclidean Geometry" reuse their exact
  // Grade 11 names (a genuine deepening, not a new skill) and so
  // already match the entries above -- no new entry needed for those
  // three.
  "Sequences and Series": [
    { label: "Σ", insert: "Σ" },
    { label: "Tₙ", insert: "Tₙ" },
    { label: "n", insert: "n" },
  ],
  "Functions and Inverse Functions": [
    { label: "f(x)", insert: "f(x)" },
    { label: "f⁻¹(x)", insert: "f⁻¹(x)" },
    { label: "x", insert: "x" },
  ],
  "Exponential and Logarithmic Functions": [
    { label: "log", insert: "log(" },
    { label: "ln", insert: "ln(" },
    { label: "ˣ", insert: "ˣ" },
  ],
  "Trigonometry: Compound Angles": [
    { label: "sin", insert: "sin(" },
    { label: "cos", insert: "cos(" },
    { label: "tan", insert: "tan(" },
    { label: "θ", insert: "θ" },
    { label: "°", insert: "°" },
  ],
  "Trigonometry: 2D and 3D Problems": [
    { label: "sin", insert: "sin(" },
    { label: "cos", insert: "cos(" },
    { label: "tan", insert: "tan(" },
    { label: "θ", insert: "θ" },
    { label: "°", insert: "°" },
  ],
  Polynomials: [
    { label: "x", insert: "x" },
    { label: "³", insert: "³" },
    { label: "ⁿ", insert: "ⁿ" },
  ],
  "Differential Calculus": [
    { label: "f'(x)", insert: "f'(x)" },
    { label: "lim", insert: "lim(" },
    { label: "→", insert: "→" },
  ],
  "Statistics: Regression and Correlation": [
    { label: "x̄", insert: "x̄" },
    { label: "Σ", insert: "Σ" },
    { label: "ŷ", insert: "ŷ" },
  ],
  "Counting and Probability": [
    { label: "%", insert: "%" },
    { label: "∩", insert: "∩" },
    { label: "∪", insert: "∪" },
    { label: "!", insert: "!" },
  ],
  // NEW 15 Nov 2026 (ADR-022, Physical Sciences Grade 12 added): same
  // "small, topic-relevant row" convention as every Physics entry
  // above. "Electric Circuits" reuses its exact Grade 11 name and
  // already has an entry above -- not repeated here.
  "Momentum and Impulse": [
    { label: "Δ", insert: "Δ" },
    { label: "kg.m/s", insert: "kg.m/s" },
  ],
  "Vertical Projectile Motion": [
    { label: "Δ", insert: "Δ" },
    { label: "m/s²", insert: "m/s²" },
  ],
  "Work, Energy and Power": [
    { label: "J", insert: "J" },
    { label: "W", insert: "W" },
  ],
  "Doppler Effect": [
    { label: "λ", insert: "λ" },
    { label: "Hz", insert: "Hz" },
  ],
  Electrodynamics: [
    { label: "Φ", insert: "Φ" },
    { label: "ε", insert: "ε" },
  ],
  "Photoelectric Effect": [
    { label: "λ", insert: "λ" },
    { label: "Hz", insert: "Hz" },
  ],
  // NEW 19 Nov 2026 (ADR-046): the two Grade 11 physics topics added with Chemistry
  "Geometrical Optics": [
    { label: "θ", insert: "θ" },
    { label: "°", insert: "°" },
    { label: "sin", insert: "sin(" },
  ],
  "2D and 3D Wavefronts": [
    { label: "λ", insert: "λ" },
    { label: "θ", insert: "θ" },
  ],
  // NEW 15 Nov 2026 (ADR-022, Accounting Grade 12 added): same R/%
  // convenience row as every other Accounting entry above. "Fixed
  // Assets", "Inventory Systems", "Value-Added Tax (VAT)",
  // "Manufacturing Cost Accounting", and "Budgeting (Cash Budget)"
  // reuse their exact Grade 11 names and already have entries above.
  "Companies: Concepts and Ledger Accounts": [
    { label: "R", insert: "R" },
    { label: "%", insert: "%" },
  ],
  "Companies: Final Accounts and Year-End Adjustments": [
    { label: "R", insert: "R" },
    { label: "%", insert: "%" },
  ],
  "Companies: Financial Statements": [
    { label: "R", insert: "R" },
    { label: "%", insert: "%" },
  ],
  "Cash Flow Statement": [
    { label: "R", insert: "R" },
    { label: "%", insert: "%" },
  ],
  "Reconciliations (Bank, Debtors and Creditors)": [
    { label: "R", insert: "R" },
    { label: "%", insert: "%" },
  ],
  "Close Corporations": [
    { label: "R", insert: "R" },
    { label: "%", insert: "%" },
  ],
};

// NEW 19 Nov 2026 (ADR-046): one row for every Chemistry (Paper 2) topic --
// subscripts for formulas (H₂O), charges for ions, reaction arrows, and the
// units chemistry calculations use.
const CHEMISTRY_SYMBOLS = [
  { label: "₂", insert: "₂" },
  { label: "₃", insert: "₃" },
  { label: "₄", insert: "₄" },
  { label: "⁺", insert: "⁺" },
  { label: "⁻", insert: "⁻" },
  { label: "²⁺", insert: "²⁺" },
  { label: "→", insert: " → " },
  { label: "⇌", insert: " ⇌ " },
  { label: "ΔH", insert: "ΔH" },
  { label: "mol/dm³", insert: "mol/dm³" },
  { label: "°C", insert: "°C" },
];

export default function SymbolKeyboard({ topicName, section, onInsert, onNextBox }) {
  const topicButtons =
    section && section.startsWith("Chemistry") ? CHEMISTRY_SYMBOLS : TOPIC_SYMBOLS[topicName] || [];

  return (
    <div className="symbol-keyboard" role="toolbar" aria-label="Math symbol keyboard">
      {STRUCTURE_KEYS.map((k) => (
        <button
          key={k.label}
          type="button"
          className="symbol-keyboard__structure"
          title={k.title}
          onClick={() => (k.action === "next" ? onNextBox?.() : onInsert(k.insert, k.cursor))}
        >
          {k.label}
        </button>
      ))}
      <span className="symbol-keyboard__divider" aria-hidden="true" />
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
