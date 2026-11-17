// NEW 17 Nov 2026 (code review #18).
import { describe, expect, it } from "vitest";
import { shrinkImageIfNeeded } from "../utils/shrinkImage";

describe("shrinkImageIfNeeded (code review #3)", () => {
  it("leaves PDFs and other non-photos untouched", async () => {
    const pdf = new File(["%PDF-1.4"], "worksheet.pdf", { type: "application/pdf" });
    expect(await shrinkImageIfNeeded(pdf)).toBe(pdf);
  });

  it("leaves GIFs untouched (they may be animated)", async () => {
    const gif = new File(["GIF89a"], "a.gif", { type: "image/gif" });
    expect(await shrinkImageIfNeeded(gif)).toBe(gif);
  });

  it("returns the original if the browser can't decode the image", async () => {
    const bad = new File(["not really a jpeg"], "photo.jpg", { type: "image/jpeg" });
    expect(await shrinkImageIfNeeded(bad)).toBe(bad);
  });
});
