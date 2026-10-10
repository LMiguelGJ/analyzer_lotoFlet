import { describe, expect, it } from "vitest";
import { formatDiskBytes, formatExactBytes, quotaInputError, remainingBytes } from "./settings-model";

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
