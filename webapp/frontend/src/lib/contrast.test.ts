import { describe, expect, it } from "vitest";
import { contrastRatio } from "./contrast";

describe("contrastRatio", () => {
  it("returns 1 for identical colors", () => {
    expect(contrastRatio("#171e26", "#171e26")).toBeCloseTo(1, 5);
  });

  it("returns 21 for black on white", () => {
    expect(contrastRatio("#000000", "#ffffff")).toBeCloseTo(21, 1);
  });

  it("is symmetric regardless of argument order", () => {
    const a = contrastRatio("#d0d4d8", "#171e26");
    const b = contrastRatio("#171e26", "#d0d4d8");
    expect(a).toBeCloseTo(b, 10);
  });

  it("matches the measured ratio for the app's primary text on background", () => {
    // Cross-checked against an independent WCAG relative-luminance calculation.
    expect(contrastRatio("#d0d4d8", "#171e26")).toBeCloseTo(11.27, 1);
  });
});
