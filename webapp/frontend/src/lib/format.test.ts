import { describe, expect, it } from "vitest";
import { formatDOP, formatLongDate, formatNumber, formatOutcome, formatPercent, formatSignedDOP, formatTwoDigit } from "./format";

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

describe("formatLongDate", () => {
  it("writes the date part of a draw label in plain Spanish", () => {
    expect(formatLongDate("2023-01-04 14:55")).toBe("4 de enero de 2023");
    expect(formatLongDate("2026-09-25")).toBe("25 de septiembre de 2026");
  });
  it("leaves anything that is not a date untouched", () => {
    expect(formatLongDate("sin fecha")).toBe("sin fecha");
    expect(formatLongDate("2026-13-01")).toBe("2026-13-01");
  });
});
