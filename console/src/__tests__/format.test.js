import { describe, expect, it } from "vitest";
import { ago, can } from "../format";

describe("can (ADR-051 roles)", () => {
  it("ranks agent < lead < director", () => {
    expect(can({ role: "agent" }, "agent")).toBe(true);
    expect(can({ role: "agent" }, "lead")).toBe(false);
    expect(can({ role: "lead" }, "agent")).toBe(true);
    expect(can({ role: "director" }, "lead")).toBe(true);
    expect(can(null, "agent")).toBe(false);
  });
});

describe("ago", () => {
  const now = Date.parse("2026-11-23T12:00:00Z");
  it("reads server times as UTC", () => {
    expect(ago("2026-11-23T11:30:00", now)).toBe("30 min ago");
    expect(ago("2026-11-23T09:00:00", now)).toBe("3 h ago");
    expect(ago("2026-11-20T12:00:00", now)).toBe("3 days ago");
  });
});
