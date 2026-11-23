import { describe, expect, it } from "vitest";
import { defaultWorkspace } from "../utils/staff";

const me = (o) => ({ can_manage_school: false, has_academic_access: true, allocations: [], roles: [], ...o });

describe("defaultWorkspace (ADR-044)", () => {
  it("teachers always get TEACH", () => {
    expect(defaultWorkspace(me({ allocations: [{}] }), "admin")).toBe("teach");
  });
  it("a school admin with no academic access gets ADMIN", () => {
    expect(defaultWorkspace(me({ can_manage_school: true, has_academic_access: false }), "teach")).toBe("admin");
  });
  it("a principal who teaches starts in TEACH unless they chose ADMIN", () => {
    const p = me({ can_manage_school: true, allocations: [{}] });
    expect(defaultWorkspace(p, null)).toBe("teach");
    expect(defaultWorkspace(p, "admin")).toBe("admin");
  });
  it("a principal without classes starts in ADMIN", () => {
    expect(defaultWorkspace(me({ can_manage_school: true }), null)).toBe("admin");
  });
});

import { adminLandingTab } from "../utils/staff";

describe("adminLandingTab (ADR-051)", () => {
  const r = (...roles) => me({ can_manage_school: true, roles: roles.map((role) => ({ role })) });
  it("principals and deputies land on the Overview", () => {
    expect(adminLandingTab(r("principal"))).toBe("overview");
    expect(adminLandingTab(r("deputy_principal", "school_admin"))).toBe("overview");
  });
  it("a school admin lands on Learners", () => {
    expect(adminLandingTab(r("school_admin"))).toBe("learners");
  });
  it("falls back to the Overview before /school/me loads", () => {
    expect(adminLandingTab(null)).toBe("overview");
  });
});
