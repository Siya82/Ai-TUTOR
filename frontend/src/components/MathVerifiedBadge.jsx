/*
 * The math_verified / verification_warnings badge.
 *
 * REBUILD_SPEC.md Section 1 states this explicitly as a requirement,
 * not a suggestion: "Exposed on POST /tutor/message as math_verified:
 * bool and verification_warnings: list[str]; shown as a visible badge
 * in the chat UI." Three states, matching MathGuard's own "honest
 * limitation" design (ADR-011) -- verified=true with warnings present
 * is NOT the same as a clean pass, and must look different from one,
 * or the honesty of that design is lost at the UI layer.
 */

import { useState } from "react";

export default function MathVerifiedBadge({ mathVerified, verificationWarnings }) {
  const [expanded, setExpanded] = useState(false);
  const warnings = verificationWarnings || [];

  let tone, label;
  if (mathVerified && warnings.length === 0) {
    tone = "success";
    label = "✓ Math verified";
  } else if (mathVerified && warnings.length > 0) {
    tone = "warning";
    label = "Partially checked";
  } else {
    tone = "error";
    label = "⚠ Possible error found";
  }

  return (
    <div className={`math-badge math-badge--${tone}`}>
      <button
        type="button"
        className="math-badge__label"
        onClick={() => setExpanded((e) => !e)}
        aria-expanded={expanded}
        disabled={warnings.length === 0}
      >
        {label}
        {warnings.length > 0 && <span className="math-badge__caret">{expanded ? " ▲" : " ▼"}</span>}
      </button>
      {expanded && warnings.length > 0 && (
        <ul className="math-badge__warnings">
          {warnings.map((w, i) => (
            <li key={i}>{w}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
