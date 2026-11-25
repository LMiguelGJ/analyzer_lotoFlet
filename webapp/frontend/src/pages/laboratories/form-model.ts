import type { LaboratoryConfig, LaboratoryOptions, RankingParams, StakeStyle } from "../../api/laboratories";
import { stakeLabel } from "../reference-labs/lab-model";

export const SYSTEMS = [
  { value: "transition", label: "Transición" },
  { value: "cold", label: "Fríos" },
  { value: "select_interpretable", label: "Selector interpretable" },
  { value: "mix", label: "Mezclas" },
  { value: "ensemble", label: "Ensemble" },
  { value: "parity", label: "Paridad" },
] as const;
export const CHANCE_LIST_ID = "chance_express";
/** One entry of the system selector; `reason` explains why an unavailable system cannot be picked. */
export interface SystemChoice { value: string; label: string; available: boolean; reason?: string }

/** Chance Express keeps its archived six systems; other lists offer what the options endpoint reports. */
export function systemChoices(options: LaboratoryOptions): SystemChoice[] {
  if (options.list.id === CHANCE_LIST_ID) return SYSTEMS.map((system) => ({ value: system.value, label: system.label, available: true }));
  return options.systems.map((system) => ({ value: system.id, label: system.label, available: system.available !== false, reason: system.reason }));
}
const STAKE_STYLE_IDS: StakeStyle[] = ["bold", "ladder", "flat", "martingale", "paroli", "dalembert", "fibonacci", "oscars_grind"];
export const STAKE_STYLES: { value: StakeStyle; label: string }[] = STAKE_STYLE_IDS.map((value) => ({ value, label: stakeLabel(value) }));
/** Styles the form offers; the server's labels win when it reports them, the local map covers older servers. */
export function stakeChoices(options: LaboratoryOptions): { value: StakeStyle; label: string }[] {
  const reported = new Map((options.stake_styles ?? []).map((style) => [style.id, style.label]));
  return STAKE_STYLES.map((style) => ({ value: style.value, label: reported.get(style.value) ?? style.label }));
}

export const PRIZE_FIELDS = ["prize_1", "prize_2", "prize_3", "prize_4", "prize_5"] as const;
export type FormField =
  | "name" | "system" | "coverage" | "stake_style" | "capital" | "goal" | "max_session_draws" | "max_stake_per_number"
  | "rp_window" | "rp_half_life" | "rp_scope" | "rp_components" | "rp_tie_break"
  | (typeof PRIZE_FIELDS)[number] | "window_start" | "window_end";
export type FormValues = Record<FormField, string>;
export type FormErrors = Partial<Record<FormField, string>>;

/** Prefills mirror the archived reference setup; every field stays editable. */
export const DEFAULT_FORM: FormValues = {
  name: "",
  system: "transition",
  coverage: "1",
  stake_style: "bold",
  capital: "2000",
  goal: "2800",
  max_session_draws: "",
  max_stake_per_number: "",
  // Ranking parameters: empty = the system's default (500 draws, first place, fixed tie-break, all components).
  rp_window: "", rp_half_life: "", rp_scope: "", rp_components: "", rp_tie_break: "",
  prize_1: "80", prize_2: "8", prize_3: "4", prize_4: "2", prize_5: "1",
  window_start: "2025-09-02 05:10",
  window_end: "2026-09-25 18:20",
};

/** The prize ids a list with `positions` numbers per draw uses (never more than five). */
export function prizeFieldsFor(positions: number): (typeof PRIZE_FIELDS)[number][] {
  return PRIZE_FIELDS.slice(0, Math.max(1, Math.min(positions, PRIZE_FIELDS.length)));
}

/** Initial form for the active list: its default prizes, window and first usable system. */
export function buildDefaultForm(options: LaboratoryOptions): FormValues {
  if (options.list.id === CHANCE_LIST_ID && options.prizes.length === 5 && options.window.start && options.window.end) {
    const form = { ...DEFAULT_FORM };
    options.prizes.forEach((prize, index) => { form[PRIZE_FIELDS[index]] = String(prize); });
    form.window_start = options.window.start; form.window_end = options.window.end;
    return form;
  }
  const choices = systemChoices(options);
  const system = (choices.find((choice) => choice.available && choice.value === "cold") ?? choices.find((choice) => choice.available))?.value ?? DEFAULT_FORM.system;
  const form: FormValues = { ...DEFAULT_FORM, system, prize_1: "", prize_2: "", prize_3: "", prize_4: "", prize_5: "" };
  options.prizes.slice(0, PRIZE_FIELDS.length).forEach((prize, index) => { form[PRIZE_FIELDS[index]] = String(prize); });
  if (options.window.start) form.window_start = options.window.start;
  if (options.window.end) form.window_end = options.window.end;
  return form;
}

/** Bold, ladder and Oscar's Grind size their stake from the first prize minus the coverage; the progressions can only go broke without it. */
function needsPrizeAboveCoverage(style: string): boolean {
  return ["bold", "ladder", "oscars_grind", "martingale", "paroli", "dalembert", "fibonacci"].includes(style);
}

const MAX_NAME_BYTES = 120;
const SAFE_MAX = Number.MAX_SAFE_INTEGER;
export const MAX_SESSION_DRAWS_LIMIT = 10000;
export const MAX_STAKE_PER_NUMBER_LIMIT = 1000000;
const WINDOW = /^(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2})$/;

function positiveInt(raw: string): number | null {
  if (!/^\d+$/.test(raw.trim())) return null;
  const value = Number(raw.trim());
  return Number.isSafeInteger(value) && value >= 1 && value <= SAFE_MAX ? value : null;
}
function validWindow(raw: string): boolean {
  const match = WINDOW.exec(raw);
  if (!match) return false;
  const [year, month, day, hour, minute] = match.slice(1).map(Number);
  const date = new Date(Date.UTC(year, month - 1, day, hour, minute));
  return date.getUTCFullYear() === year && date.getUTCMonth() === month - 1 && date.getUTCDate() === day
    && date.getUTCHours() === hour && date.getUTCMinutes() === minute;
}

export const RANKING_WINDOW_MIN = 10;
export const RANKING_WINDOW_MAX = 5000;
export const HALF_LIFE_MIN = 5;
export const HALF_LIFE_MAX = 5000;
/** The seven rankings an ensemble can vote with, in the server's order. */
export const ENSEMBLE_COMPONENTS = ["cold", "freq_hist", "freq_recent", "decay", "transition", "overdue", "digits"] as const;

/** Which system parameters the form shows for a system; parity and Chance Express take none. */
export function rankingParamFields(system: string, listId: string): { window: boolean; halfLife: boolean; scope: boolean; components: boolean; tieBreak: boolean } {
  const none = { window: false, halfLife: false, scope: false, components: false, tieBreak: false };
  if (listId === CHANCE_LIST_ID || system === "parity" || !(ENSEMBLE_COMPONENTS as readonly string[]).concat("ensemble").includes(system)) return none;
  return {
    window: ["freq_recent", "freq_hist", "digits", "transition"].includes(system),
    halfLife: system === "decay",
    scope: system === "cold" || system === "freq_hist",
    components: system === "ensemble",
    tieBreak: true,
  };
}

/** The components currently chosen in the form (empty = the default seven). */
export function chosenComponents(raw: string): string[] {
  return raw.split(",").filter((item) => item !== "");
}

function rankingInt(raw: string, low: number, high: number): number | null {
  if (!/^\d+$/.test(raw.trim())) return null;
  const value = Number(raw.trim());
  return value >= low && value <= high ? value : null;
}

/** Spanish short text of the chosen params for headers and the sidebar, e.g. " · vida media 300". */
export function rankingParamsText(params: RankingParams | undefined): string {
  if (!params) return "";
  const parts: string[] = [];
  if (params.half_life !== undefined) parts.push(`vida media ${params.half_life}`);
  if (typeof params.window === "number") parts.push(`ventana ${params.window}`);
  if (params.fallback_window !== undefined) parts.push(`ventana ${params.fallback_window}`);
  if (params.scope !== undefined) parts.push(params.scope === "any" ? "mirar cualquier lugar" : "mirar 1.er lugar");
  if (params.components !== undefined) parts.push(`${params.components.length} componentes`);
  if (params.tie_break === "seeded") parts.push("desempate variado");
  return parts.map((part) => ` · ${part}`).join("");
}

export type ParseResult =
  | { ok: true; value: { name: string; config: LaboratoryConfig } }
  | { ok: false; errors: FormErrors };

/** Client-side mirror of the server rules; the server remains the authority. */
export function parseLaboratoryForm(values: FormValues, positions: number = PRIZE_FIELDS.length, listId: string = CHANCE_LIST_ID): ParseResult {
  const prizeFields = prizeFieldsFor(positions);
  const errors: FormErrors = {};
  const name = values.name;
  if (name.trim() === "" || name !== name.trim()) errors.name = "Escribí un nombre sin espacios al inicio ni al final.";
  else if (new TextEncoder().encode(name).length > MAX_NAME_BYTES) errors.name = "El nombre admite hasta 120 bytes UTF-8.";
  // eslint-disable-next-line no-control-regex
  else if (/[\u0000-\u001f\u007f-\u009f]/.test(name)) errors.name = "El nombre no puede incluir caracteres de control.";

  const coverage = positiveInt(values.coverage);
  if (coverage === null || coverage > 50) errors.coverage = "La cobertura es un entero entre 1 y 50.";
  else if (values.system === "parity" && coverage !== 50) errors.coverage = "Paridad requiere los 50 números.";

  const capital = positiveInt(values.capital);
  if (capital === null) errors.capital = "El capital es un entero positivo.";
  else if (coverage !== null && capital < coverage) errors.capital = "El capital debe cubrir al menos una unidad por número.";

  const goal = positiveInt(values.goal);
  if (goal === null) errors.goal = "La meta es un entero positivo.";
  else if (capital !== null && goal <= capital) errors.goal = "La meta debe ser mayor que el capital inicial.";

  let maxSessionDraws: number | null = null;
  if (values.max_session_draws.trim() !== "") {
    maxSessionDraws = positiveInt(values.max_session_draws);
    if (maxSessionDraws === null || maxSessionDraws > MAX_SESSION_DRAWS_LIMIT) {
      maxSessionDraws = null;
      errors.max_session_draws = `Escribí un número entero entre 1 y ${MAX_SESSION_DRAWS_LIMIT}, o dejalo vacío para no poner límite.`;
    }
  }

  let maxStakePerNumber: number | null = null;
  if (values.max_stake_per_number.trim() !== "") {
    maxStakePerNumber = positiveInt(values.max_stake_per_number);
    if (maxStakePerNumber === null || maxStakePerNumber > MAX_STAKE_PER_NUMBER_LIMIT) {
      maxStakePerNumber = null;
      errors.max_stake_per_number = `Escribí un número entero entre 1 y ${MAX_STAKE_PER_NUMBER_LIMIT}, o dejalo vacío para no poner tope.`;
    }
  }

  const prizes = prizeFields.map((field) => {
    const prize = positiveInt(values[field]);
    if (prize === null) errors[field] = "El premio es un entero positivo.";
    return prize;
  });
  if (!errors.prize_1 && prizes[0] !== null && coverage !== null && needsPrizeAboveCoverage(values.stake_style) && prizes[0] <= coverage) {
    errors.prize_1 = "El primer premio debe ser mayor que la cobertura.";
  }

  const rankingParams: RankingParams = {};
  const fields = rankingParamFields(values.system, listId);
  if (fields.window && values.rp_window.trim() !== "") {
    const window = rankingInt(values.rp_window, RANKING_WINDOW_MIN, RANKING_WINDOW_MAX);
    if (window === null) errors.rp_window = `La ventana es un entero entre ${RANKING_WINDOW_MIN} y ${RANKING_WINDOW_MAX} sorteos, o dejala vacía para usar la de por defecto.`;
    else if (values.system === "transition") rankingParams.fallback_window = window;
    else rankingParams.window = window;
  }
  if (fields.halfLife && values.rp_half_life.trim() !== "") {
    const halfLife = rankingInt(values.rp_half_life, HALF_LIFE_MIN, HALF_LIFE_MAX);
    if (halfLife === null) errors.rp_half_life = `La vida media es un entero entre ${HALF_LIFE_MIN} y ${HALF_LIFE_MAX} sorteos, o dejala vacía para usar 500.`;
    else rankingParams.half_life = halfLife;
  }
  if (fields.scope && values.rp_scope !== "") rankingParams.scope = values.rp_scope === "any" ? "any" : "position";
  if (fields.components && values.rp_components !== "") {
    const components = chosenComponents(values.rp_components).filter((item) => (ENSEMBLE_COMPONENTS as readonly string[]).includes(item));
    if (components.length < 2) errors.rp_components = "Elegí al menos 2 componentes, o dejá todos para usar el Ensamble de siempre.";
    else rankingParams.components = ENSEMBLE_COMPONENTS.filter((item) => components.includes(item));
  }
  if (fields.tieBreak && values.rp_tie_break === "seeded") rankingParams.tie_break = "seeded";

  if (!validWindow(values.window_start)) errors.window_start = "Usá el formato AAAA-MM-DD HH:MM con una fecha real.";
  if (!validWindow(values.window_end)) errors.window_end = "Usá el formato AAAA-MM-DD HH:MM con una fecha real.";
  else if (!errors.window_start && values.window_end < values.window_start) errors.window_end = "El fin debe ser posterior al inicio.";

  if (Object.keys(errors).length > 0 || coverage === null || capital === null || goal === null || prizes.some((p) => p === null)) {
    return { ok: false, errors };
  }
  return {
    ok: true,
    value: {
      name,
      config: {
        schema_version: 1,
        system: values.system,
        coverage,
        stake_style: values.stake_style as StakeStyle,
        capital,
        goal,
        prizes: prizes as number[],
        window_start: values.window_start,
        window_end: values.window_end,
        ...(maxSessionDraws === null ? {} : { max_session_draws: maxSessionDraws }),
        ...(maxStakePerNumber === null ? {} : { max_stake_per_number: maxStakePerNumber }),
        ...(Object.keys(rankingParams).length === 0 ? {} : { ranking_params: rankingParams }),
      },
    },
  };
}
