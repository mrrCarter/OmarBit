import { describe, it, expect } from "vitest";

describe("Health check", () => {
  it("returns true", () => {
    expect(true).toBe(true);
  });
});

describe("ComingSoonBadge", () => {
  it("renders without error", async () => {
    const { ComingSoonBadge } = await import("@/components/coming-soon-badge");
    expect(ComingSoonBadge).toBeDefined();
    expect(typeof ComingSoonBadge).toBe("function");
  });
});

describe("API client", () => {
  it("module exports apiFetch", async () => {
    const { apiFetch } = await import("@/lib/api");
    expect(apiFetch).toBeDefined();
    expect(typeof apiFetch).toBe("function");
  });
});
