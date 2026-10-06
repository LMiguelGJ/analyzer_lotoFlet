import type { BacktestInputs, BacktestReport, CreateBacktestBody, GameSettings, StakingStyle } from "../../api/types";

export type BacktestSystem = "transition" | "cold" | "select_interpretable" | "mix" | "ensemble";
export interface BacktestDraft {
  name: string; system: BacktestSystem; parity: boolean; coverage: string; staking: StakingStyle; strategyName?: string; savedName?: string;
  numbers: string; positions: string; prizes: string[]; minStake: string; capital: string; goal: string;
  inputs?: BacktestInputs;
}

const systemNames: Record<BacktestSystem, string> = {
  transition: "Transición", cold: "Fríos", select_interpretable: "Selector automático", mix: "Mezclas", ensemble: "Ensemble",
};
const whole = (value: string) => /^(0|[1-9]\d*)$/.test(value) ? Number(value) : NaN;
const systems = Object.keys(systemNames) as BacktestSystem[];

export function hydrateBacktestDraft(config: CreateBacktestBody): BacktestDraft | null {
  const strategy = config?.strategy;
  if (typeof config?.name !== "string" || !config.name || !strategy || typeof strategy.name !== "string"
    || !config.game || !config.conditions || !config.inputs
    || typeof config.inputs.history_sha256 !== "string" || !config.inputs.history_sha256
    || typeof config.inputs.rankings_sha256 !== "string" || !config.inputs.rankings_sha256
    || !Number.isSafeInteger(strategy.coverage) || !["flat", "ladder", "bold"].includes(strategy.staking)
    || (strategy.selector !== "parity" && (strategy.selector !== "system" || !systems.includes(strategy.system as BacktestSystem)))) return null;
  const { game, conditions } = config;
  if (!Number.isSafeInteger(game.numbers) || !Number.isSafeInteger(game.positions) || !Array.isArray(game.prizes)
    || game.prizes.length !== game.positions || !game.prizes.every(Number.isSafeInteger) || !Number.isSafeInteger(game.min_stake)
    || !Number.isSafeInteger(conditions.capital) || !Number.isSafeInteger(conditions.goal)) return null;
  return {
    name: config.name, savedName: config.name,
    system: (strategy.system && systems.includes(strategy.system as BacktestSystem) ? strategy.system : "transition") as BacktestSystem,
    parity: strategy.selector === "parity", coverage: String(strategy.coverage), staking: strategy.staking, strategyName: strategy.name,
    numbers: String(game.numbers), positions: String(game.positions), prizes: game.prizes.map(String),
    minStake: String(game.min_stake), capital: String(conditions.capital), goal: String(conditions.goal),
    inputs: { ...config.inputs },
  };
}

export function validateBacktestDraft(draft: BacktestDraft, game?: GameSettings): string[] {
  const errors: string[] = [];
  const coverage = whole(draft.coverage);
  const numbers = whole(draft.numbers);
  const positions = whole(draft.positions);
  const prizes = draft.prizes.map(whole);
  const capital = whole(draft.capital);
  const goal = whole(draft.goal);
  const minimum = whole(draft.minStake);
  const maxNumbers = game?.numbers ?? numbers;
  if (!draft.name.trim() || draft.name.trim().length > 80) errors.push("Escribí un nombre de hasta 80 caracteres para reconocer la corrida.");
  if (!Number.isSafeInteger(numbers) || numbers < 2 || numbers > 1000) errors.push("Ingresá entre 2 y 1.000 números posibles; la regla debe coincidir con el sorteo.");
  if (!Number.isSafeInteger(positions) || positions < 1 || positions > 16) errors.push("Ingresá entre 1 y 16 posiciones de premio.");
  if (!Number.isSafeInteger(coverage) || coverage < 1) errors.push("La cobertura debe ser un número entero desde 1.");
  else if (coverage > maxNumbers) errors.push(`La cobertura supera los ${maxNumbers} números posibles; la estrategia no puede elegirlos.`);
  else if (draft.parity && coverage > 50) errors.push("Paridad puede cubrir hasta 50 números; con más no hay números para seleccionar.");
  if (prizes.length !== positions || prizes.some((prize) => !Number.isSafeInteger(prize) || prize < 1)) errors.push("Ingresá un premio entero de al menos RD$1 por cada posición.");
  if (!Number.isSafeInteger(minimum) || minimum < 1) errors.push("La apuesta mínima debe ser un entero de al menos RD$1.");
  if (!Number.isSafeInteger(capital) || capital < 1) errors.push("El capital debe ser un entero de al menos RD$1.");
  if (!Number.isSafeInteger(goal) || goal < 2 || goal <= capital) errors.push("La meta debe ser mayor que el capital; sin esa diferencia la sesión no puede terminar al alcanzarla.");
  return errors;
}

export function buildBacktestBody(draft: BacktestDraft, _game: GameSettings, inputs: BacktestInputs): CreateBacktestBody {
  const systemName = draft.parity ? "Tu par/impar" : systemNames[draft.system];
  return {
    name: draft.name === draft.savedName ? draft.name : draft.name.trim(),
    strategy: {
      name: draft.strategyName ?? systemName, selector: draft.parity ? "parity" : "system",
      system: draft.parity ? null : draft.system,
      coverage: Number(draft.coverage), staking: draft.staking,
    },
    game: {
      numbers: Number(draft.numbers), positions: Number(draft.positions),
      prizes: draft.prizes.map(Number), min_stake: Number(draft.minStake),
    },
    conditions: { capital: Number(draft.capital), goal: Number(draft.goal) },
    inputs,
  };
}

export const stakingDescriptions: Record<StakingStyle, string> = {
  flat: "Plana: RD$1 a cada número.",
  ladder: "Escalera: recupera lo apostado + RD$10 al acertar el primero.",
  bold: "Audaz: apuesta para que un primer premio alcance la meta.",
};

export function backtestScenarioName(report: BacktestReport) {
  const strategy = report.config?.strategy;
  if (strategy?.selector === "parity") return "Tu par/impar";
  return strategy?.name || systemNames[strategy?.system as BacktestSystem] || report.name || "Corrida histórica";
}
