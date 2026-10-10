import { describe, expect, it } from "vitest";
import { formatDOP, formatNumber, formatOutcome, formatPercent, formatSignedDOP, formatTwoDigit } from "./format";

describe("financial and Dominican formatting", () => {
  it("formats signed money with RD$ and never emits negative zero", () => {
    expect(formatSignedDOP(2000)).toBe("+RD$2.000");
    expect(formatSignedDOP(-1250)).toBe("−RD$1.250");
    expect(formatSignedDOP(-0)).toBe("+RD$0");
    expect(formatDOP(2000)).toBe("+RD$2.000");
    expect(formatDOP(-0)).toBe("+RD$0");
  });

  it("formats Dominican numbers and signed percentage values", () => {
    expect(formatNumber(105426)).toBe("105.426");
    expect(formatPercent(12.5)).toBe("+12,5 %");
    expect(formatPercent(-0)).toBe("+0,0 %");
    expect(formatPercent(-25)).toBe("−25,0 %");
  });

  it("labels each persisted outcome in Spanish", () => {
    expect(formatOutcome("goal")).toBe("Meta");
    expect(formatOutcome("ruin")).toBe("Quiebra");
    expect(formatOutcome("limit")).toBe("Límite");
    expect(formatOutcome("incomplete")).toBe("Incompleta");
  });

  it("keeps Quiniela numbers zero-padded", () => expect(formatTwoDigit(4)).toBe("04"));
});
