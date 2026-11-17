import { describe, expect, it } from "vitest";
import { bytesToMbInput, formatDiskBytes, formatExactBytes, formatSize, mbInputToBytes, parsePrizes, positionLabel, quotaInputError, quotaMbError, remainingBytes, usagePercent } from "./settings-model";

describe("exact storage quantities", () => {
  it("subtracts and formats exact decimal byte strings without Number precision loss", () => {
    expect(remainingBytes("9223372036854775807", "9007199254740993")).toBe("9214364837600034814");
    expect(formatExactBytes("9007199254740993")).toBe("9,007,199,254,740,993 bytes");
  });
  it("labels unsafe numeric disk metrics as approximate and rejects unreliable values", () => {
    expect(formatDiskBytes(Number.MAX_SAFE_INTEGER)).toBe("9,007,199,254,740,991 bytes");
    expect(formatDiskBytes(9007199254740993)).toBe("Valor aproximado: ≈ 9,007,199,254,740,992 bytes");
    expect(formatDiskBytes(Number.NaN)).toBe("Precisión no disponible");
    expect(formatDiskBytes(Number.POSITIVE_INFINITY)).toBe("Precisión no disponible");
    expect(formatDiskBytes(-1)).toBe("Precisión no disponible");
    expect(formatExactBytes("9007199254740993")).toBe("9,007,199,254,740,993 bytes");
  });
  it.each(["", "0", "01", "+1", "1e3", "１２", "1.0", "9223372036854775808"])("rejects noncanonical/out-of-range quota %s", (value) => {
    expect(quotaInputError(value)).toBeTruthy();
  });
  it("accepts canonical positive decimal values through SQLite's signed maximum", () => {
    expect(quotaInputError("1")).toBeNull();
    expect(quotaInputError("9223372036854775807")).toBeNull();
    expect(quotaInputError("1234567890123456789")).toBeNull();
  });
});

describe("plain-language storage helpers", () => {
  it("formats sizes in MB/GB with Spanish decimals", () => {
    expect(formatSize("0")).toBe("0 MB");
    expect(formatSize("524288000")).toBe("500 MB");
    expect(formatSize("1610612736")).toBe("1,5 GB");
    expect(formatSize("1000")).toBe("menos de 0,1 MB");
  });
  it("converts the MB editor value to the exact byte string and back", () => {
    expect(mbInputToBytes("2048")).toBe("2147483648");
    expect(mbInputToBytes("0,5")).toBe("524288");
    expect(mbInputToBytes("1.25")).toBe("1310720");
    expect(bytesToMbInput("2147483648")).toBe("2048");
    expect(bytesToMbInput("1310720")).toBe("1,25");
  });
  it.each(["", "0", "abc", "-1", "1,234", "1e3"])("rejects %j as a quota in MB", (value) => {
    expect(quotaMbError(value)).toBeTruthy();
  });
  it("computes the used share without exceeding 100", () => {
    expect(usagePercent("524288000", "2147483648")).toBe(25);
    expect(usagePercent("5000", "1000")).toBe(100);
  });
  it("accepts only whole prizes from 1 to 10000", () => {
    expect(parsePrizes(["60", "8", "4"])).toEqual([60, 8, 4]);
    for (const bad of [["0"], ["10001"], ["1.5"], ["-1"], [""], ["60,0"]]) expect(parsePrizes(bad)).toBeNull();
    expect(positionLabel(0)).toBe("1.er número");
    expect(positionLabel(1)).toBe("2.º número");
    expect(positionLabel(2)).toBe("3.er número");
  });
});
