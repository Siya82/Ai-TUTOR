// NEW 17 Nov 2026 (code review #18): first frontend tests.
import { afterEach, describe, expect, it, vi } from "vitest";
import { changePassword, fetchSchoolMe, login, setUnauthorizedHandler } from "../api";

function respond(status, body) {
  globalThis.fetch = vi.fn().mockResolvedValue({
    ok: status < 400,
    status,
    json: () => Promise.resolve(body),
  });
}

afterEach(() => {
  setUnauthorizedHandler(null);
  vi.restoreAllMocks();
});

describe("session-ended handling (code review #14)", () => {
  it("calls the handler when an authenticated call gets a 401", async () => {
    const handler = vi.fn();
    setUnauthorizedHandler(handler);
    respond(401, { detail: "Session ended. Please log in again." });
    await expect(fetchSchoolMe("tok")).rejects.toMatchObject({ status: 401 });
    expect(handler).toHaveBeenCalledOnce();
  });

  it("does not treat a wrong password at login as a session ending", async () => {
    const handler = vi.fn();
    setUnauthorizedHandler(handler);
    respond(401, { detail: "Incorrect student number or password" });
    await expect(login({ schoolId: "s", studentNumber: "1", password: "x" })).rejects.toThrow(
      "Incorrect student number or password"
    );
    respond(401, { detail: "Current password is incorrect" });
    await expect(
      changePassword({ token: "t", currentPassword: "x", newPassword: "abcdefgh" })
    ).rejects.toThrow("Current password is incorrect");
    expect(handler).not.toHaveBeenCalled();
  });

  it("turns a validation error list into one readable message", async () => {
    respond(422, { detail: [{ msg: "String should have at most 4000 characters" }] });
    await expect(fetchSchoolMe("tok")).rejects.toThrow("String should have at most 4000 characters");
  });
});
