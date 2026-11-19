// NEW 19 Nov 2026 (ADR-042)
import { describe, expect, it } from "vitest";
import { chunkToLatex, hasStructuredMath, nextSlot, segmentMath, toTutorText } from "../utils/mathInput";

describe("chunkToLatex", () => {
  it("turns bracketed fractions into \\frac", () => {
    expect(chunkToLatex("(x+1)/(x-2)")).toBe("\\frac{x+1}{x-2}");
  });
  it("handles simple and spaced fractions", () => {
    expect(chunkToLatex("3/4")).toBe("\\frac{3}{4}");
    expect(chunkToLatex("(2x) / (3)")).toBe("\\frac{2x}{3}");
  });
  it("nests fractions, roots and powers", () => {
    expect(chunkToLatex("(1/(x+1))/(2)")).toBe("\\frac{\\frac{1}{x+1}}{2}");
    expect(chunkToLatex("√(x²+1)")).toBe("\\sqrt{x^{2}+1}");
    expect(chunkToLatex("2^(n-1)")).toBe("2^{n-1}");
  });
  it("keeps an unfinished fraction readable while typing", () => {
    expect(chunkToLatex("(x+1)/(")).toBe("\\frac{x+1}{\\square}");
    expect(chunkToLatex("()/()")).toBe("\\frac{\\square}{\\square}");
  });
  it("maps symbols", () => {
    expect(chunkToLatex("sin(θ)")).toContain("\\sin");
    expect(chunkToLatex("x ≤ 3")).toBe("x \\le 3");
  });
});

describe("toTutorText", () => {
  it("leaves plain questions untouched", () => {
    const q = "What is a variable? I have 2 questions.";
    expect(toTutorText(q)).toBe(q);
  });
  it("wraps the maths in a sentence", () => {
    expect(toTutorText("Simplify (x+1)/(x-2) please")).toBe("Simplify $\\frac{x+1}{x-2}$ please");
  });
  it("keeps punctuation outside the maths", () => {
    expect(toTutorText("Why is 3/4 bigger than 2/3?")).toBe("Why is $\\frac{3}{4}$ bigger than $\\frac{2}{3}$?");
  });
  it("joins an equation across spaces", () => {
    expect(toTutorText("Solve x/2 + 1 = 5")).toBe("Solve $\\frac{x}{2} + 1 = 5$");
  });
});

describe("helpers", () => {
  it("detects structured maths", () => {
    expect(hasStructuredMath("solve x = 3")).toBe(false);
    expect(hasStructuredMath("solve x² = 9")).toBe(true);
  });
  it("finds the next box", () => {
    const t = "(x+1)/()";
    expect(nextSlot(t, 1)).toBe(7);
    expect(nextSlot(t, 7)).toBe(null);
  });
  it("segments keep prose as text", () => {
    const segs = segmentMath("a fraction like 1/2");
    expect(segs.filter((s) => s.type === "math").length).toBe(1);
    expect(segs[0]).toEqual({ type: "text", value: "a" });
  });
});
