import { describe, expect, it } from "vitest";
import type { GameSettings } from "../../api/types";
import { buildBacktestBody, hydrateBacktestDraft, validateBacktestDraft, type BacktestDraft } from "./backtest-model";

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

  it("round-trips every saved field and keeps a deep copy of source hashes", () => {
    const config = {
      name: "Guardada", strategy: { name: "Tu par/impar", selector: "parity" as const, system: null, coverage: 17, staking: "ladder" as const },
      game: { numbers: 77, positions: 3, prizes: [91, 13, 5], min_stake: 7 },
      conditions: { capital: 3400, goal: 9100 },
      inputs: { history_sha256: "c".repeat(64), rankings_sha256: "d".repeat(64) },
    };
    const hydrated = hydrateBacktestDraft(config);
    expect(hydrated).not.toBeNull();
    expect(buildBacktestBody(hydrated!, game, hydrated!.inputs!)).toEqual(config);
    expect(hydrated!.inputs).not.toBe(config.inputs);
    expect(hydrateBacktestDraft({ ...config, strategy: { ...config.strategy, selector: "system", system: null } } as never)).toBeNull();
  });

  it("rejects saved strategies outside the historical wire contract", () => {
    const config = { name: "Guardada", strategy: { name: "Stored", selector: "parity", coverage: 17, staking: "flat" },
      game: { numbers: 100, positions: 1, prizes: [1], min_stake: 1 }, conditions: { capital: 2, goal: 3 },
      inputs: { history_sha256: "a", rankings_sha256: "b" } };
    expect(hydrateBacktestDraft({ ...config, strategy: { ...config.strategy, coverage: 51 } } as never)).toBeNull();
    expect(hydrateBacktestDraft({ ...config, strategy: { ...config.strategy, system: "cold" } } as never)).toBeNull();
    expect(hydrateBacktestDraft({ ...config, strategy: { ...config.strategy, components: [] } } as never)).toBeNull();
    expect(hydrateBacktestDraft({ ...config, strategy: { ...config.strategy, selector: "blend" } } as never)).toBeNull();
    expect(hydrateBacktestDraft({ ...config, strategy: { ...config.strategy, staking: "other" } } as never)).toBeNull();
    expect(hydrateBacktestDraft({ ...config, strategy: { ...config.strategy, selector: "system", system: "random" } } as never)).toBeNull();
    expect(hydrateBacktestDraft({ ...config, strategy: { ...config.strategy, selector: "system", system: "cold", components: [] } } as never)).toBeNull();
  });

  it.each([1, 17, 49, 50])("validates and hydrates historical parity coverage %s without coercion", (coverage) => {
    const parity = { ...draft, parity: true, coverage: String(coverage), strategyName: " Paridad guardada " };
    expect(validateBacktestDraft(parity)).toEqual([]);
    const body = buildBacktestBody(parity, game, { history_sha256: "a".repeat(64), rankings_sha256: "b".repeat(64) });
    const hydrated = hydrateBacktestDraft(body)!;
    expect(hydrated.coverage).toBe(String(coverage));
    expect(buildBacktestBody(hydrated, game, hydrated.inputs!)).toEqual(body);
  });

  it.each([0, -1, 17.5, 51, NaN, Infinity, -Infinity])("rejects invalid historical parity coverage %s in drafts and saved runs", (coverage) => {
    const parity = { ...draft, parity: true, coverage: String(coverage) };
    expect(validateBacktestDraft(parity)).not.toEqual([]);
    expect(hydrateBacktestDraft(buildBacktestBody(parity, game, { history_sha256: "a", rankings_sha256: "b" }))).toBeNull();
  });

  it("bounds parity by the native game universe as well as optional game settings", () => {
    const parity = { ...draft, parity: true, numbers: "17", coverage: "17" };
    expect(validateBacktestDraft(parity, game)).toEqual([]);
    const overflow = { ...parity, coverage: "18" };
    expect(validateBacktestDraft(overflow)).toContain("La cobertura supera los 17 números posibles; la estrategia no puede elegirlos.");
    expect(validateBacktestDraft(overflow, game)).not.toEqual([]);
    expect(validateBacktestDraft(parity, { ...game, numbers: 16 })).not.toEqual([]);
    expect(hydrateBacktestDraft(buildBacktestBody(overflow, game, { history_sha256: "a", rankings_sha256: "b" }))).toBeNull();
  });

  it("preserves the saved ranking selector and its exact strategy label", () => {
    const config = {
      name: "Guardada", strategy: { name: "Etiqueta original", selector: "system" as const, system: "mix" as const, coverage: 22, staking: "flat" as const },
      game: { numbers: 100, positions: 5, prizes: [80, 8, 4, 2, 1], min_stake: 1 },
      conditions: { capital: 2000, goal: 2800 },
      inputs: { history_sha256: "a".repeat(64), rankings_sha256: "b".repeat(64) },
    };
    const hydrated = hydrateBacktestDraft(config)!;
    expect(hydrated.system).toBe("mix");
    expect(buildBacktestBody(hydrated, game, hydrated.inputs!)).toEqual(config);
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
