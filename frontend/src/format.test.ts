import { describe, expect, it } from "vitest";
import { money, moneyCents, safeSourceUrl, title, reasonLabel } from "./format";

describe("exact financial display", () => {
  it("preserves cents without binary-float conversion", () => {
    expect(money("97382000.00")).toBe("$97,382,000.00");
    expect(money("-2618000.00", true)).toBe("−$2,618,000.00");
    expect(money("2618000.00", true)).toBe("+$2,618,000.00");
    expect(money("999999999999.99")).toBe("$999,999,999,999.99");
    expect(moneyCents("-0.00")).toBe(0n);
  });
  it("rejects malformed amounts rather than inventing zero", () => {
    expect(() => money("NaN")).toThrow();
    expect(() => money("1.234")).toThrow();
  });
  it("allows only safe supported source links", () => {
    expect(safeSourceUrl("javascript:alert(1)")).toBeNull();
    expect(safeSourceUrl("https://evil.test/")).toBeNull();
    expect(
      safeSourceUrl("https://www.federalreserve.gov/newsevents/a.htm"),
    ).toContain("federalreserve.gov");
    expect(
      safeSourceUrl("https://name:secret@www.federalreserve.gov/"),
    ).toBeNull();
  });
  it("labels speculation and machine review reasons plainly", () => {
    expect(
      title({ event_subtype: "rate_hike", assertion_status: "speculative" }),
    ).toMatch(/Possible/);
    expect(reasonLabel("source_not_verified")).toMatch(/verified/i);
  });
});
