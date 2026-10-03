import type { SelectorKind, SettlementMode, StakingStyle } from "../api/types";

/**
 * Presentation-only vocabulary fixed by the plan `claridad-interfaz-80-20.md`
 * (decisions 3-9). These are purely display strings for existing enum
 * values; they carry no domain logic and do not change internal keys,
 * catalog names, defaults, or API payloads. `Record<Kind, string>` typing
 * means an enum value added to `api/types` without a matching entry here
 * fails typecheck.
 */

/** Decision 3: visual-only mapping of the selector kind. Catalog system names are untouched. */
export const SELECTOR_LABELS: Record<SelectorKind, string> = {
  system: "Un sistema de selección",
  blend: "Combinación de sistemas",
  random: "Selección al azar reproducible",
  parity: "Selección por paridad (par/impar)",
};

/** Decision 4: staking style names are kept as-is ("Plana", "Escalera", "Audaz"). */
export const STAKING_LABELS: Record<StakingStyle, string> = {
  flat: "Plana",
  ladder: "Aumentar por pasos",
  bold: "Apuesta más alta",
};

/** Decision 4: restates only the mechanics already described in StrategyEditor.tsx; no new claims. */
export const STAKING_DESCRIPTIONS: Record<StakingStyle, string> = {
  flat: "Importe base constante por número.",
  ladder: "Ajusta la apuesta según los resultados anteriores.",
  bold: "Aumenta la apuesta según la estrategia elegida.",
};

/** Decision 5: `all`/`best` values and settlement rules are unchanged; only the presented text is new. */
export const SETTLEMENT_LABELS: Record<SettlementMode, string> = {
  all: "Sumar los premios",
  best: "Contar solo el mayor premio por número",
};

/** Decision 4: field label for the staking selector. */
export const FIELD_LABEL_STAKING = "Forma de ajustar la apuesta";

/** Decision 5: field label for the settlement selector. */
export const FIELD_LABEL_SETTLEMENT = "Cómo contar los premios";

/** Decision 6: still the same required field, no new generation or defaults. */
export const FIELD_LABEL_SEED = "Código de repetición";
export const FIELD_HELP_SEED = "El mismo código permite repetir la selección aleatoria con las mismas condiciones. Ingresá un entero de 0 a 9.007.199.254.740.991; se comparte por sorteo entre todas las estrategias.";

/** Decision 7: shows exclusively `result.delta` received from the API, no frontend subtraction. */
export const FIELD_LABEL_DELTA = "Cambio respecto del inicio";
export const FIELD_HELP_DELTA = "Diferencia entre el saldo final y el capital inicial";

/**
 * Decision 9: static caveat placed near the summary/table. It complements,
 * and must not replace or weaken, each page's existing qualifier about
 * already-investigated historical data and the lack of independent
 * validation (e.g. DetailPage.tsx, ComparisonPage.tsx).
 */
export const HISTORICAL_CAVEAT = "Simulación con datos históricos: no predice resultados futuros ni garantiza rentabilidad.";
