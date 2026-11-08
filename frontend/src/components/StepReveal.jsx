/*
 * Animated modality: step-reveal/wipe presentation of the solving steps,
 * via Framer Motion.
 *
 * REBUILD NOTE (8 Nov 2026, step 7): REBUILD_SPEC.md Section 3 describes
 * this only as "via Framer Motion ... a 'step-reveal/wipe' presentation
 * of the solving steps" -- framer-motion itself wasn't even in the
 * recovered package.json (added this step, per the spec's own note).
 * The exact transition/interaction design is this rebuild's own,
 * written to match that one-line description, not recovered.
 *
 * Splits the response on the same "---" step-divider convention
 * utils/tts.js already uses to turn dividers into a spoken pause --
 * reusing an existing, already-recovered convention rather than
 * inventing a second one.
 */

import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import MarkdownMessage from "./MarkdownMessage";

const STEP_DIVIDER = /\n\s*---\s*\n/;

export function splitIntoSteps(text) {
  return text
    .split(STEP_DIVIDER)
    .map((s) => s.trim())
    .filter((s) => s.length > 0);
}

export default function StepReveal({ text }) {
  const steps = splitIntoSteps(text);
  // Each StepReveal instance is created for one fixed message and never
  // reused for a different `text` afterwards (see ChatScreen.jsx -- each
  // chat message is a distinct, immutable array entry), so the reveal
  // count only ever needs its initial value, not an effect that resets
  // it on every `text` change.
  const [revealedCount, setRevealedCount] = useState(1);

  const atEnd = revealedCount >= steps.length;

  return (
    <div className="step-reveal">
      <AnimatePresence initial={false}>
        {steps.slice(0, revealedCount).map((step, index) => (
          <motion.div
            key={index}
            className="step-reveal__step"
            initial={{ opacity: 0, x: -16 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.35, ease: "easeOut" }}
          >
            <MarkdownMessage text={step} />
          </motion.div>
        ))}
      </AnimatePresence>

      {!atEnd && (
        <div className="step-reveal__controls">
          <button type="button" onClick={() => setRevealedCount((c) => c + 1)}>
            Reveal next step ({revealedCount} / {steps.length})
          </button>
          <button type="button" className="step-reveal__show-all" onClick={() => setRevealedCount(steps.length)}>
            Show all
          </button>
        </div>
      )}
    </div>
  );
}
