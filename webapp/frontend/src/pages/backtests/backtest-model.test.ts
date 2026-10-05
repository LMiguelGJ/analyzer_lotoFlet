import { describe, expect, it } from "vitest";
import type { GameSettings } from "../../api/types";
import { buildBacktestBody, validateBacktestDraft, type BacktestDraft } from "./backtest-model";

const game: GameSettings = { name: "Reglas actuales", numbers: 100, positions: 5, prizes: [80, 8, 4, 2, 1], allows_repeats: true, minimum_stake: 1, source: "stored" };
const draft: BacktestDraft = {
  name: "Escenario general", system: "transition", parity: false, coverage: "50", staking: "bold",
  numbers: "100", positions: "5", prizes: ["80", "8", "4", "2", "1"], minStake: "1", capital: "2000", goal: "2800",
};

describe("historical backtest configuration", () => {
  it("builds the exact backend request and accepts a configurable reference scenario", () => {
    expect(validateBacktestDraft(draft)).toEqual([]);
    expect(buildBacktestBody(draft, { ...game, numbers: 100 }, { history_sha256: "a".repeat(64), rankings_sha256: "b".repeat(64) })).toEqual({
      name: "Escenario general",
      strategy: { name: "Transición", selector: "system", system: "transition", coverage: 50, staking: "bold" },
      game: { numbers: 100, positions: 5, prizes: [80, 8, 4, 2, 1], min_stake: 1 },
      conditions: { capital: 2000, goal: 2800 },
      inputs: { history_sha256: "a".repeat(64), rankings_sha256: "b".repeat(64) },
    });
  });

  it("omits ranking system for parity and reports concrete consequences for invalid rules", () => {
    const parity = { ...draft, parity: true, coverage: "51" };
    expect(validateBacktestDraft(parity, game)).toContain("Paridad puede cubrir hasta 50 números; con más no hay números para seleccionar.");
    expect(buildBacktestBody({ ...parity, coverage: "50" }, game, { history_sha256: "a".repeat(64), rankings_sha256: "b".repeat(64) }).strategy)
      .toEqual({ name: "Tu par/impar", selector: "parity", system: null, coverage: 50, staking: "bold" });
    expect(validateBacktestDraft({ ...draft, coverage: "101" }, game)).toContain("La cobertura supera los 100 números posibles; la estrategia no puede elegirlos.");
    expect(validateBacktestDraft({ ...draft, goal: "2000" })).toContain("La meta debe ser mayor que el capital; sin esa diferencia la sesión no puede terminar al alcanzarla.");
  });
});
