import type { Catalog, Conditions, ExperimentRequest, SelectorKind, StakingStyle, Strategy } from "../../api/types";

export interface ConditionsDraft {
  name: string; start_draw: string; capital: string; goal: string; settlement: "all" | "best";
  max_bets: string; max_minutes: string; seed: string;
}
export interface StrategyDraft {
  id: number; name: string; selector: SelectorKind; system: string; components: { system: string; weight: string }[];
  coverage: string; staking: StakingStyle;
}
/** A friendly Spanish message plus the raw server technical detail, shown as secondary text. */
export interface FieldError { message: string; detail?: string }
export type ErrorValue = string | FieldError;
export type Errors = Record<string, ErrorValue>;
export function errorMessage(entry: ErrorValue | undefined): string | undefined {
  return typeof entry === "string" ? entry : entry?.message;
}
export function errorDetail(entry: ErrorValue | undefined): string | undefined {
  return typeof entry === "string" ? undefined : entry?.detail;
}
export const initialConditions: ConditionsDraft = {
  name: "", start_draw: "", capital: "2000", goal: "2800", settlement: "all", max_bets: "12", max_minutes: "", seed: "",
};
export function newStrategy(id: number): StrategyDraft {
  return { id, name: "", selector: "system", system: "", components: [{ system: "", weight: "" }, { system: "", weight: "" }], coverage: "1", staking: "flat" };
}
export function initialStrategy(id: number): StrategyDraft {
  return { id, name: "", selector: "blend", system: "", components: [{ system: "transition", weight: "60" }, { system: "cold", weight: "40" }], coverage: "10", staking: "flat" };
}

/** The single scalar or component sub-field that changed between two drafts of the same
 * strategy, in the `strategies.N.<field>` dotted form used by Errors keys, so an edit can
 * clear exactly the server error it addresses without discarding unrelated ones. */
export function diffStrategyKey(previous: StrategyDraft, next: StrategyDraft): string | null {
  if (previous.name !== next.name) return "name";
  if (previous.selector !== next.selector) return "selector";
  if (previous.system !== next.system) return "system";
  if (previous.coverage !== next.coverage) return "coverage";
  if (previous.staking !== next.staking) return "staking";
  if (previous.components.length !== next.components.length) return "components";
  for (let index = 0; index < next.components.length; index += 1) {
    if (previous.components[index]?.system !== next.components[index].system) return `components.${index}.system`;
    if (previous.components[index]?.weight !== next.components[index].weight) return `components.${index}.weight`;
  }
  return null;
}

/** Parse only exact decimal integers, bounded with BigInt to avoid Number's lossy rounding at the edges of the range. */
export function integer(value: string, min: bigint, max: bigint): number | null {
  if (!/^[0-9]+$/.test(value)) return null;
  const parsed = BigInt(value);
  return parsed >= min && parsed <= max ? Number(parsed) : null;
}
/** The same explicit trim used by normalizeStrategyName, applied before storage.
 * Replaces JS's built-in String.prototype.trim(), which strips U+FEFF where Python's
 * str.strip() doesn't (and vice versa for U+0085): using each side's default definition
 * let the stored name and the duplicate-detection key drift apart. */
export function trimName(name: string): string {
  return name.replace(NAME_TRIM_RE, "");
}
function named(value: string): boolean { const trimmed = trimName(value); return trimmed.length > 0 && trimmed.length <= 80; }
const money = 1_000_000_000_000n;
const MAX_SEED = BigInt(Number.MAX_SAFE_INTEGER);

// Unicode category Zs (space separators) plus ASCII control whitespace, spelled out
// explicitly because JS's String.prototype.trim() and Python's str.strip() disagree on
// some format characters (e.g. U+FEFF): relying on each language's built-in whitespace
// definition would let the two sides drift apart again. Mirrors
// webapp/backend/laboratorio/domain/contracts.py's _NAME_TRIM_RE exactly.
const NAME_TRIM_RE = /^[ \t\n\r\f\v\u00A0\u1680\u2000-\u200A\u2028\u2029\u202F\u205F\u3000]+|[ \t\n\r\f\v\u00A0\u1680\u2000-\u200A\u2028\u2029\u202F\u205F\u3000]+$/g;

/** Canonical form used only to detect duplicate strategy names, never to store a name.
 * Mirrors contracts.py's normalize_strategy_name: NFKC folds compatibility variants
 * (ligatures, fullwidth letters, combining sequences); the explicit trim charset removes
 * leading/trailing spaces without depending on trim()'s built-in definition; toUpperCase()
 * then toLowerCase() folds case including special mappings (e.g. german eszett) that
 * toLocaleLowerCase() folds asymmetrically. */
export function normalizeStrategyName(name: string): string {
  return trimName(name.normalize("NFKC")).toUpperCase().toLowerCase();
}
export function validateConditions(draft: ConditionsDraft, available: string[]): Errors {
  const errors: Errors = {};
  if (!named(draft.name)) errors.name = "Ingresá un nombre de 1 a 80 caracteres.";
  if (!available.includes(draft.start_draw)) errors.start_draw = "Elegí un sorteo con ranking disponible.";
  const capital = integer(draft.capital, 1n, money);
  const goal = integer(draft.goal, 2n, money);
  if (capital === null) errors.capital = "Ingresá pesos enteros entre 1 y 1.000.000.000.000.";
  if (goal === null) errors.goal = "Ingresá pesos enteros entre 2 y 1.000.000.000.000.";
  else if (capital !== null && goal <= capital) errors.goal = "La meta es el saldo final y debe superar el capital inicial.";
  if (draft.max_bets !== "" && integer(draft.max_bets, 1n, 10_000_000n) === null)
    errors.max_bets = "Ingresá un entero entre 1 y 10.000.000 o dejalo vacío.";
  if (draft.max_minutes !== "" && integer(draft.max_minutes, 1n, 100_000_000n) === null)
    errors.max_minutes = "Ingresá un entero entre 1 y 100.000.000 o dejalo vacío.";
  if (integer(draft.seed, 0n, MAX_SEED) === null)
    errors.seed = "Ingresá un entero entre 0 y 9.007.199.254.740.991.";
  return errors;
}
export function validateStrategies(drafts: StrategyDraft[], catalog: Catalog): Errors {
  const errors: Errors = {};
  if (drafts.length < 1 || drafts.length > 5) errors.strategies = "Agregá entre 1 y 5 configuraciones.";
  const names = new Set<string>();
  drafts.forEach((draft, index) => {
    const path = `strategies.${index}`;
    if (!named(draft.name)) errors[`${path}.name`] = "Ingresá un nombre de 1 a 80 caracteres.";
    else if (names.has(normalizeStrategyName(draft.name))) errors[`${path}.name`] = "El nombre debe ser único entre las configuraciones.";
    names.add(normalizeStrategyName(draft.name));
    if (!catalog.selectors.includes(draft.selector)) errors[`${path}.selector`] = "Método no disponible.";
    if (draft.selector === "system" && !Object.hasOwn(catalog.systems, draft.system))
      errors[`${path}.system`] = "Elegí un sistema disponible.";
    if (draft.selector === "blend") {
      if (draft.components.length < 2 || draft.components.length > 13) errors[`${path}.components`] = "Elegí entre 2 y 13 sistemas.";
      const systems = new Set<string>();
      let sum = 0;
      draft.components.forEach((component, componentIndex) => {
        const key = `${path}.components.${componentIndex}`;
        if (!Object.hasOwn(catalog.systems, component.system) || systems.has(component.system))
          errors[`${key}.system`] = "Elegí un sistema disponible y distinto.";
        systems.add(component.system);
        const weight = integer(component.weight, 1n, 99n);
        if (weight === null) errors[`${key}.weight`] = "Ingresá un peso entero entre 1 y 99%.";
        else sum += weight;
      });
      if (sum !== 100) errors[`${path}.components`] = "Los pesos deben sumar 100%.";
    }
    if (draft.selector !== "parity" && !catalog.coverages.includes(Number(draft.coverage)))
      errors[`${path}.coverage`] = "Elegí una cobertura disponible.";
    if (!["flat", "ladder", "bold"].includes(draft.staking)) errors[`${path}.staking`] = "Elegí un tipo de apuesta.";
  });
  return errors;
}
// Rebuild editable, independent strings from the immutable saved request. Never
// coerce a missing saved value into a plausible default: validation will reject it.
export function draftFromRequest(request: ExperimentRequest): { conditions: ConditionsDraft; strategies: StrategyDraft[] } {
  const source = request.conditions;
  return {
    conditions: {
      name: request.name, start_draw: source.start_draw, capital: String(source.capital), goal: String(source.goal),
      settlement: source.settlement, max_bets: source.max_bets == null ? "" : String(source.max_bets),
      max_minutes: source.max_minutes == null ? "" : String(source.max_minutes), seed: String(source.seed),
    },
    strategies: request.strategies.map((strategy, index) => ({
      id: index + 1, name: strategy.name, selector: strategy.selector, system: strategy.system ?? "",
      components: strategy.components?.map((component) => ({ system: component.system, weight: String(component.weight) })) ?? [],
      coverage: String(strategy.coverage), staking: strategy.staking,
    })),
  };
}

export function draftFromStrategy(strategy: Strategy, id: number): StrategyDraft {
  return {
    id, name: strategy.name, selector: strategy.selector, system: strategy.system ?? "",
    components: strategy.components?.map((component) => ({ system: component.system, weight: String(component.weight) })) ?? [],
    coverage: String(strategy.coverage), staking: strategy.staking,
  };
}

export function buildStrategy(draft: StrategyDraft, catalog: Catalog): Strategy {
  return {
    name: trimName(draft.name), selector: draft.selector,
    ...(draft.selector === "system" ? { system: draft.system } : {}),
    ...(draft.selector === "blend" ? { components: draft.components.map((component) => ({ system: component.system, weight: Number(component.weight) })) } : {}),
    coverage: draft.selector === "parity" ? catalog.parity_coverage : Number(draft.coverage), staking: draft.staking,
  };
}

export function buildRequest(conditions: ConditionsDraft, drafts: StrategyDraft[], catalog: Catalog): ExperimentRequest {
  const common: Conditions = {
    start_draw: conditions.start_draw, capital: Number(conditions.capital), goal: Number(conditions.goal),
    settlement: conditions.settlement, max_bets: conditions.max_bets === "" ? null : Number(conditions.max_bets),
    max_minutes: conditions.max_minutes === "" ? null : Number(conditions.max_minutes),
    seed: Number(conditions.seed),
  };
  const strategies: Strategy[] = drafts.map((draft) => buildStrategy(draft, catalog));
  return { name: trimName(conditions.name), conditions: common, strategies };
}
