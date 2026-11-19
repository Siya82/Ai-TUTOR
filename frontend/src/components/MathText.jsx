/*
 * NEW 19 Nov 2026 (ADR-042). Renders learner-typed maths with KaTeX:
 *  - <MathText text="Simplify $\frac{x+1}{x-2}$" />  for sent messages
 *    (the $...$ form toTutorText produced), and
 *  - <MathPreview draft={...} />  the live strip above the question box,
 *    showing what the learner typed as real fractions/powers/roots.
 */
import katex from "katex";
import { segmentMath, hasStructuredMath } from "../utils/mathInput";

function Katex({ latex }) {
  // \displaystyle: full-size stacked fractions, easier to read than inline ones.
  const html = katex.renderToString(`\\displaystyle ${latex}`, {
    throwOnError: false,
    strict: "ignore",
    output: "html",
  });
  // KaTeX output is generated from our own converted string, not raw HTML.
  return <span className="math-inline" dangerouslySetInnerHTML={{ __html: html }} />;
}

export function MathText({ text }) {
  if (!text || !text.includes("$")) return <>{text}</>;
  const parts = text.split(/(\$[^$]+\$)/g);
  return (
    <>
      {parts.map((p, i) =>
        p.startsWith("$") && p.endsWith("$") && p.length > 2 ? <Katex key={i} latex={p.slice(1, -1)} /> : p
      )}
    </>
  );
}

export function MathPreview({ draft }) {
  if (!hasStructuredMath(draft)) return null;
  return (
    <div className="math-preview" aria-live="polite">
      <span className="math-preview__label">THUTOra will read:</span>
      <span className="math-preview__body">
        {segmentMath(draft).map((s, i) => (s.type === "math" ? <Katex key={i} latex={s.value} /> : s.value))}
      </span>
    </div>
  );
}
