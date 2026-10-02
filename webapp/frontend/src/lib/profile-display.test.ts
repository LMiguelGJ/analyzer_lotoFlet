import { describe, expect, it } from "vitest";
import { formatProfileMoney, profileOutcome } from "./profile-display";
import type { ProfileRunResult } from "../api/types";

describe("profile read-only display", () => {
  it("formats exact integer minor units without rounding or assuming RD$", () => {
    expect(formatProfileMoney(12345, "USD", 2)).toBe("USD 123.45");
    expect(formatProfileMoney(-5, "EUR", 2)).toBe("-EUR 0.05");
    expect(formatProfileMoney(0, "DOP", 0)).toBe("DOP 0");
    expect(formatProfileMoney(1, "XTS", 6)).toBe("XTS 0.000001");
    expect(formatProfileMoney(Number.MAX_SAFE_INTEGER, "USD", 2)).toBe("USD 90,071,992,547,409.91");
  });

  it("rejects unsafe or non-integral units and unsupported scales instead of losing precision", () => {
    expect(() => formatProfileMoney(Number.MAX_SAFE_INTEGER + 1, "USD", 2)).toThrow(RangeError);
    expect(() => formatProfileMoney(1.5, "USD", 2)).toThrow(RangeError);
    expect(() => formatProfileMoney(1, "USD", 7)).toThrow(RangeError);
  });

  it("labels the schema-4 recovery ladder exhaustion collision", () => {
    const result: ProfileRunResult = { schema_version: 4, profile_id: "custom", profile_revision: 1,
      outcome: "limit", collisions: ["recovery_round_limit"], elapsed_draws: 4, bet_draws: 4,
      wagered: 400, paid: 0, final_balance: 600, delta: -400 };
    expect(profileOutcome(result)).toBe("Límite de sesión (límite de rondas de recuperación)");
  });
  it("separates saved outcome and collision reasons in Spanish without inventing a result", () => {
    const result: ProfileRunResult = {
      schema_version: 1, profile_id: "test", profile_revision: 1, outcome: "limit",
      collisions: ["max_bet_draws", "max_elapsed_draws"], elapsed_draws: 3, bet_draws: 2,
      wagered: 200, paid: 0, final_balance: 300, delta: -200,
    };
    expect(profileOutcome(result)).toBe("Límite de sesión (límite de sorteos apostados, límite de sorteos transcurridos)");
    expect(profileOutcome({ ...result, outcome: "cancelled", collisions: [] })).toBe("Cancelado durante la sesión");
  });
});
