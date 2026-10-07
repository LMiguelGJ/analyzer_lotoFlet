import type { Strategy } from "../../api/types";
import type { StrategyDraft } from "../new-experiment/model";
import type { BacktestDraft } from "./backtest-model";

const systemLabels: Record<string, string> = { transition: "Transición", cold: "Fríos", select_interpretable: "Selector automático", mix: "Mezclas", ensemble: "Ensemble" };
const systems = new Set(Object.keys(systemLabels));

export function historicalStrategyToDraft(strategy: Strategy, numbers = 1000): StrategyDraft | null {
  if (!strategy || typeof strategy.name !== "string" || !strategy.name.trim() || !Number.isSafeInteger(strategy.coverage)
    || !["flat", "ladder", "bold"].includes(strategy.staking)) return null;
  if (strategy.selector === "parity") {
    if (strategy.coverage < 1 || strategy.coverage > 50 || strategy.coverage > numbers || strategy.system != null || strategy.components != null) return null;
    return { id: 1, name: strategy.name, selector: "parity", system: "", components: [], coverage: String(strategy.coverage), staking: strategy.staking };
  }
  if (strategy.selector !== "system" || typeof strategy.system !== "string" || !systems.has(strategy.system)
    || strategy.components != null) return null;
  return { id: 1, name: strategy.name, selector: "system", system: strategy.system, components: [], coverage: String(strategy.coverage), staking: strategy.staking };
}

export function strategyDraftFromBacktest(draft: BacktestDraft): StrategyDraft {
  return {
    id: 1, name: draft.strategyName ?? (draft.parity ? "Tu par/impar" : systemLabels[draft.system] ?? ""),
    selector: draft.parity ? "parity" : "system", system: draft.parity ? "" : draft.system,
    components: [], coverage: draft.coverage, staking: draft.staking,
  };
}

export function applyHistoricalStrategyDraft(current: BacktestDraft, strategy: StrategyDraft): BacktestDraft | null {
  if (strategy.components.length || !Number.isSafeInteger(Number(strategy.coverage))
    || !["flat", "ladder", "bold"].includes(strategy.staking)) return null;
  const changedMethod = strategy.selector !== (current.parity ? "parity" : "system") || (!current.parity && strategy.system !== current.system);
  const autoName = current.strategyName ?? (current.parity ? "Tu par/impar" : systemLabels[current.system]);
  const strategyName = !current.strategyName && changedMethod && strategy.name === autoName ? undefined : strategy.name;
  if (strategy.selector === "parity") {
    const coverage = Number(strategy.coverage);
    if (coverage < 1 || coverage > 50 || coverage > Number(current.numbers) || strategy.system !== "") return null;
    return { ...current, parity: true, coverage: strategy.coverage, staking: strategy.staking, strategyName };
  }
  if (strategy.selector !== "system" || !systems.has(strategy.system)) return null;
  return { ...current, parity: false, system: strategy.system as BacktestDraft["system"], coverage: strategy.coverage, staking: strategy.staking, strategyName };
}
