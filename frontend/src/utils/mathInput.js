/*
 * NEW 19 Nov 2026 (ADR-042, fractions and formulas in the question box).
 *
 * Learners type maths on a normal one-line box with the symbol keyboard's
 * help: a fraction is (top)/(bottom), a power is x^(n) or x², a root is
 * √(x). This module finds the maths in what they typed and turns it into
 * LaTeX, so that
 *   - the live preview above the box shows real stacked fractions,
 *   - the question THUTOra receives is unambiguous ($\frac{x+1}{x-2}$
 *     instead of "(x+1)/(x-2)"), and
 *   - the sent message shows as maths in the chat.
 *
 * Plain questions with no fraction, power or root are left exactly as
 * typed (toTutorText returns them unchanged), so nothing changes for
 * ordinary chat.
 */

const SYMBOLS = {
  "×": "\\times ",
  "÷": "\\div ",
  "*": "\\times ",
  "·": "\\cdot ",
  "±": "\\pm ",
  "≤": "\\le ",
  "≥": "\\ge ",
  "≠": "\\ne ",
  "≈": "\\approx ",
  "θ": "\\theta ",
  "π": "\\pi ",
  "Δ": "\\Delta ",
  "λ": "\\lambda ",
  "μ": "\\mu ",
  "Ω": "\\Omega ",
  "Σ": "\\Sigma ",
  "Φ": "\\Phi ",
  "ε": "\\varepsilon ",
  "∠": "\\angle ",
  "∥": "\\parallel ",
  "≅": "\\cong ",
  "∩": "\\cap ",
  "∪": "\\cup ",
  "→": "\\to ",
  "°": "^{\\circ}",
  "%": "\\%",
  "−": "-",
};
const SUPERSCRIPTS = { "⁰": "0", "¹": "1", "²": "2", "³": "3", "⁴": "4", "⁵": "5", "⁶": "6", "⁷": "7", "⁸": "8", "⁹": "9", "ⁿ": "n", "⁺": "+", "⁻": "-" };
const SUBSCRIPTS = { "₀": "0", "₁": "1", "₂": "2", "₃": "3", "ₙ": "n" };
const FUNCTIONS = ["sin", "cos", "tan", "log", "ln"];

// --- one maths chunk -> LaTeX -----------------------------------------------

function matchParen(s, open) {
  let depth = 0;
  for (let i = open; i < s.length; i += 1) {
    if (s[i] === "(") depth += 1;
    else if (s[i] === ")") {
      depth -= 1;
      if (depth === 0) return i;
    }
  }
  return -1; // unclosed: the learner is still typing
}

/** Reads one operand at i: a (group), a number, a letter (with ' or x̄), or √/function. */
function readOperand(s, i) {
  if (i >= s.length) return null;
  const ch = s[i];
  if (ch === "(") {
    const close = matchParen(s, i);
    const inner = close === -1 ? s.slice(i + 1) : s.slice(i + 1, close);
    // An empty box (the learner hasn't typed into it yet) shows as a small square.
    const latex = inner.trim() ? chunkToLatex(inner) : "\\square";
    return { latex, end: close === -1 ? s.length : close + 1, group: true };
  }
  if (ch === "√") {
    const arg = readOperand(s, i + 1);
    if (!arg) return { latex: "\\sqrt{\\square }", end: i + 1 };
    return { latex: `\\sqrt{${arg.latex}}`, end: arg.end };
  }
  const num = /^\d+(?:[.,]\d+)?/.exec(s.slice(i));
  if (num) return { latex: num[0], end: i + num[0].length };
  for (const f of FUNCTIONS) {
    if (s.startsWith(f, i)) return { latex: `\\${f} `, end: i + f.length };
  }
  if (/[a-zA-Z]/.test(ch)) {
    if (s[i + 1] === "̄") return { latex: `\\bar{${ch}}`, end: i + 2 }; // x̄
    return { latex: ch, end: i + 1 };
  }
  if (SYMBOLS[ch] && !"×÷*·±≤≥≠≈→%−".includes(ch)) return { latex: SYMBOLS[ch].trim(), end: i + 1 };
  return null;
}

/** Converts one chunk of typed maths (no surrounding prose) to LaTeX. */
export function chunkToLatex(s) {
  let out = "";
  let i = 0;
  while (i < s.length) {
    const ch = s[i];
    if (ch === " ") {
      out += " ";
      i += 1;
      continue;
    }
    if (ch === "^") {
      const exp = readOperand(s, i + 1);
      out += exp ? `^{${exp.latex}}` : "^{\\square }";
      i = exp ? exp.end : i + 1;
      continue;
    }
    if (SUPERSCRIPTS[ch]) {
      let sup = "";
      while (i < s.length && SUPERSCRIPTS[s[i]]) sup += SUPERSCRIPTS[s[i++]];
      out += `^{${sup}}`;
      continue;
    }
    if (SUBSCRIPTS[ch]) {
      let sub = "";
      while (i < s.length && SUBSCRIPTS[s[i]]) sub += SUBSCRIPTS[s[i++]];
      out += `_{${sub}}`;
      continue;
    }
    const operand = readOperand(s, i);
    if (operand) {
      // A fraction: operand / operand. Spaces around "/" are allowed.
      let j = operand.end;
      while (s[j] === " ") j += 1;
      if (s[j] === "/") {
        let k = j + 1;
        while (s[k] === " ") k += 1;
        const den = readOperand(s, k);
        out += `\\frac{${operand.latex}}{${den ? den.latex : "\\square "}}`;
        i = den ? den.end : s.length;
        continue;
      }
      out += operand.group ? `\\left(${operand.latex}\\right)` : operand.latex;
      i = operand.end;
      continue;
    }
    if (ch === "/") {
      out += "/";
      i += 1;
      continue;
    }
    out += SYMBOLS[ch] ?? ch;
    i += 1;
  }
  return out.replace(/\s+/g, " ").trim();
}

// --- finding the maths inside a sentence --------------------------------------

const STRUCTURAL = /[/^√⁰¹²³⁴⁵⁶⁷⁸⁹ⁿ⁺⁻₀₁₂₃ₙ]/;
const STRONG = /[\d/^√⁰¹²³⁴⁵⁶⁷⁸⁹ⁿ⁺⁻₀₁₂₃ₙ=<>≤≥≠×÷±()θπΔλμΩΣΦε°∠∥≅∩∪→]/;
const OPERATOR = /^[+\-−=×÷*·±<>≤≥≠≈/]$/;
const TRAILING = /[?!.,;:]+$/;

function splitTokens(text) {
  // Whitespace-separated tokens, but an unclosed "(" keeps joining tokens
  // until it closes, so "(x + 1)/(x - 2)" stays one token.
  const raw = text.split(/(\s+)/);
  const tokens = [];
  let buf = "";
  let depth = 0;
  for (const piece of raw) {
    if (/^\s+$/.test(piece)) {
      if (depth > 0) buf += piece;
      else if (buf) {
        tokens.push(buf);
        buf = "";
      }
      continue;
    }
    buf += piece;
    for (const ch of piece) {
      if (ch === "(") depth += 1;
      else if (ch === ")") depth = Math.max(0, depth - 1);
    }
  }
  if (buf) tokens.push(buf);
  return tokens;
}

/**
 * Splits text into [{ type: "text" | "math", value }]. A "math" value is
 * LaTeX. Single letters count as maths only next to an operator
 * ("x = 3"), so "a" in an English sentence stays text.
 */
export function segmentMath(text) {
  const tokens = splitTokens(text || "").map((tok) => {
    const trail = TRAILING.exec(tok);
    const core = trail && !tok.endsWith(")") ? tok.slice(0, -trail[0].length) : tok;
    return { core, trail: core === tok ? "" : tok.slice(core.length) };
  });
  const math = tokens.map((t) => STRONG.test(t.core) && !/^[A-Za-z]+[.,]?$/.test(t.core));
  tokens.forEach((t, i) => {
    if (OPERATOR.test(t.core)) {
      const prev = tokens[i - 1];
      const next = tokens[i + 1];
      const isOperand = (x) => x && (/^[A-Za-z]$/.test(x.core) || STRONG.test(x.core));
      if (isOperand(prev) && isOperand(next) && !prev.trail) {
        math[i - 1] = true;
        math[i] = true;
        math[i + 1] = true;
      }
    }
  });
  const segments = [];
  let run = [];
  const flushRun = () => {
    if (!run.length) return;
    const typed = run.map((t) => t.core + t.trail).join(" ");
    const last = run[run.length - 1];
    const body = run.map((t, idx) => (idx === run.length - 1 ? t.core : t.core + t.trail)).join(" ");
    segments.push({ type: "math", value: chunkToLatex(body), typed, structural: STRUCTURAL.test(typed) });
    if (last.trail) segments.push({ type: "text", value: last.trail });
    run = [];
  };
  tokens.forEach((t, i) => {
    if (math[i]) {
      run.push(t);
      return;
    }
    flushRun();
    segments.push({ type: "text", value: t.core + t.trail });
  });
  flushRun();
  // Re-insert single spaces between segments (punctuation hugs the maths before it).
  const spaced = [];
  segments.forEach((seg, i) => {
    if (i > 0 && !(seg.type === "text" && /^[?!.,;:]+$/.test(seg.value))) spaced.push({ type: "text", value: " " });
    spaced.push(seg);
  });
  return spaced;
}

/** True when the text has a fraction, power or root worth previewing. */
export function hasStructuredMath(text) {
  return segmentMath(text).some((s) => s.type === "math" && s.structural);
}

/**
 * What to send the tutor: unchanged when there's no fraction/power/root;
 * otherwise each maths chunk wrapped as $LaTeX$ (which THUTOra's replies
 * also use, and the chat renders).
 */
export function toTutorText(text) {
  if (!hasStructuredMath(text)) return text;
  return segmentMath(text)
    .map((s) => (s.type === "math" ? `$${s.value}$` : s.value))
    .join("");
}

/** Moves the caret to the next empty or fillable box: just after the next "(". */
export function nextSlot(text, caret) {
  const close = text.indexOf(")", caret);
  const searchFrom = close === -1 ? caret : close;
  const open = text.indexOf("(", searchFrom);
  return open === -1 ? null : open + 1;
}
