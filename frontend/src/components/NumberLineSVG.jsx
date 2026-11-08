/*
 * Visual modality: an SVG number-line renderer for inequality solutions.
 *
 * REBUILD NOTE (8 Nov 2026, step 7): REBUILD_SPEC.md Section 3 describes
 * this only as "an SVG number-line renderer, implying at least one new
 * component rendering number-line SVGs for applicable problem types" --
 * no further detail survived. This is a genuine (re)write, scoped
 * deliberately narrow and honest about its limits, in the same spirit as
 * MathGuard's own "honest limitation" design (ADR-011): it only renders
 * a number line when it can confidently parse an already-simplified,
 * single-variable inequality (e.g. "x < -3", "2 <= x < 7") straight out
 * of one of the response's own $$...$$ blocks. It never tries to SOLVE
 * an inequality itself (that's MathGuard's job, in Python, with sympy) --
 * if nothing in the response is already in that simplified shape, it
 * renders nothing rather than guessing.
 */

import { useMemo } from "react";

const REL_OPS = ["<=", ">=", "<", ">"];

function stripMathDelimiters(block) {
  return block
    .replace(/\\left|\\right/g, "")
    .replace(/\\leq/g, "<=")
    .replace(/\\geq/g, ">=")
    .replace(/\\le/g, "<=")
    .replace(/\\ge/g, ">=")
    .trim();
}

/**
 * Extracts the LAST $$...$$ block in `text` that is already a simplified,
 * single-variable inequality -- "x < -3", "x >= 5", or a double-sided
 * range "2 <= x < 7" -- with purely numeric bounds. Returns null if none
 * of the blocks match this narrow, confident shape.
 */
export function extractSimplifiedInequality(text) {
  const blocks = [...text.matchAll(/\$\$(.+?)\$\$/gs)].map((m) => stripMathDelimiters(m[1]));

  const singlePattern = /^([a-zA-Z]+)\s*(<=|>=|<|>)\s*(-?\d+(?:\.\d+)?)$/;
  const rangePattern =
    /^(-?\d+(?:\.\d+)?)\s*(<=|<)\s*([a-zA-Z]+)\s*(<=|<)\s*(-?\d+(?:\.\d+)?)$/;

  let found = null;
  for (const block of blocks) {
    const single = block.match(singlePattern);
    if (single) {
      found = {
        type: "single",
        variable: single[1],
        op: single[2],
        bound: parseFloat(single[3]),
      };
      continue;
    }
    const range = block.match(rangePattern);
    if (range) {
      found = {
        type: "range",
        lower: parseFloat(range[1]),
        lowerOp: range[2],
        variable: range[3],
        upperOp: range[4],
        upper: parseFloat(range[5]),
      };
    }
  }
  return found;
}

function niceBounds(center, span) {
  const min = Math.floor(center - span);
  const max = Math.ceil(center + span);
  return [min, max];
}

export default function NumberLineSVG({ solution }) {
  const { min, max, ticks } = useMemo(() => {
    let lo, hi;
    if (solution.type === "single") {
      [lo, hi] = niceBounds(solution.bound, 6);
    } else {
      const center = (solution.lower + solution.upper) / 2;
      const span = Math.max(6, (solution.upper - solution.lower) / 2 + 3);
      [lo, hi] = niceBounds(center, span);
    }
    const step = Math.max(1, Math.round((hi - lo) / 10));
    const tickValues = [];
    for (let v = lo; v <= hi; v += step) tickValues.push(v);
    return { min: lo, max: hi, ticks: tickValues };
  }, [solution]);

  const width = 320;
  const height = 80;
  const padding = 24;
  const scale = (value) => padding + ((value - min) / (max - min)) * (width - 2 * padding);

  const renderSingle = () => {
    const x = scale(solution.bound);
    const open = solution.op === "<" || solution.op === ">";
    const rayStart = solution.op === "<" || solution.op === "<=" ? padding : x;
    const rayEnd = solution.op === "<" || solution.op === "<=" ? x : width - padding;
    return (
      <>
        <line x1={rayStart} y1={height / 2} x2={rayEnd} y2={height / 2}
              stroke="var(--color-accent)" strokeWidth="4" />
        <circle cx={x} cy={height / 2} r="6"
                fill={open ? "var(--color-background)" : "var(--color-accent)"}
                stroke="var(--color-accent)" strokeWidth="2" />
      </>
    );
  };

  const renderRange = () => {
    const xLower = scale(solution.lower);
    const xUpper = scale(solution.upper);
    const lowerOpen = solution.lowerOp === "<";
    const upperOpen = solution.upperOp === "<";
    return (
      <>
        <line x1={xLower} y1={height / 2} x2={xUpper} y2={height / 2}
              stroke="var(--color-accent)" strokeWidth="4" />
        <circle cx={xLower} cy={height / 2} r="6"
                fill={lowerOpen ? "var(--color-background)" : "var(--color-accent)"}
                stroke="var(--color-accent)" strokeWidth="2" />
        <circle cx={xUpper} cy={height / 2} r="6"
                fill={upperOpen ? "var(--color-background)" : "var(--color-accent)"}
                stroke="var(--color-accent)" strokeWidth="2" />
      </>
    );
  };

  return (
    <div className="number-line-wrapper" role="img"
         aria-label={`Number line showing the solution ${solution.variable} ${solution.type === "single" ? solution.op + " " + solution.bound : solution.lower + " " + solution.lowerOp + " " + solution.variable + " " + solution.upperOp + " " + solution.upper}`}>
      <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`}>
        <line x1={padding} y1={height / 2} x2={width - padding} y2={height / 2}
              stroke="var(--color-border)" strokeWidth="2" />
        {ticks.map((t) => (
          <g key={t}>
            <line x1={scale(t)} y1={height / 2 - 5} x2={scale(t)} y2={height / 2 + 5}
                  stroke="var(--color-text-muted)" strokeWidth="1" />
            <text x={scale(t)} y={height / 2 + 20} fontSize="10"
                  fill="var(--color-text-muted)" textAnchor="middle">{t}</text>
          </g>
        ))}
        {solution.type === "single" ? renderSingle() : renderRange()}
      </svg>
    </div>
  );
}
