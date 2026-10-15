import { describe, expect, it } from "vitest";
import { formatReturnOnWagered, returnOnWagered } from "./result-model";

describe("historical return presentation", () => {
  it.each([
    [-1482496, 30303350, "−4,89 %"],
    [50, 100, "+50,00 %"],
    [0, 100, "+0,00 %"],
    [-0, 100, "+0,00 %"],
    [-1, 1000000, "+0,00 %"],
    [0, 0, "No disponible"],
  ])("formats %s over %s as %s", (net, wagered, expected) => {
    expect(formatReturnOnWagered(returnOnWagered(net, wagered))).toBe(expected);
    if (wagered === 0) expect(returnOnWagered(net, wagered)).toBeNull();
    else expect(Object.is(returnOnWagered(net, wagered), -0)).toBe(false);
  });
  it("divides before multiplying, without an overflowing intermediate", () => {
    expect(returnOnWagered(Number.MAX_VALUE, Number.MAX_VALUE)).toBe(100);
  });
});
