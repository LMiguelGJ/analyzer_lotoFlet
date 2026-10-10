import type { CreateRunRequest, PersistedRunConfig, RunOptions, RunReport } from "../../api/types";

export interface RunForm {
  name: string; positions: string; prizes: string[]; minimumStake: string; kind: "mix" | "parity";
  components: { system: string; percent: string }[]; coverage: string; capital: string; goal: string;
  maxDraws: string; startDate: string; endDate: string; historySha: string | null;
}
export type RunFormErrors = Partial<Record<keyof RunForm | "form", string>>;

export function formatStrategyLabel(strategy: PersistedRunConfig["strategy"], systems: RunOptions["systems"]): string {
  if (strategy.kind === "parity") return `Paridad · ${strategy.coverage} números`;
  const components = strategy.components.map((item) => {
    const label = systems.find((system) => system.id === item.system)?.label ?? "Sistema no disponible";
    return `${label} ${item.percent} %`;
  });
  return `${components.length ? components.join(" + ") : "Mezcla de rankings"} · ${strategy.coverage} números`;
}

export function parseIntegerInput(value: string): number | null {
  if (!/^[0-9]+$/.test(value)) return null;
  const parsed = Number(value);
  return Number.isSafeInteger(parsed) ? parsed : null;
}

export function resizePrizes(values: string[], count: number): string[] {
  return Array.from({ length: count }, (_, index) => values[index] ?? "1");
}

export function createInitialRunForm(options: RunOptions, base?: RunReport): RunForm {
  const config = base?.config ?? options.defaults;
  return {
    name: base?.name ?? config.name ?? "",
    positions: String(config.rules?.positions ?? 3),
    prizes: resizePrizes((config.rules?.prizes ?? [60, 10, 5]).map(String), config.rules?.positions ?? 3),
    minimumStake: String(config.rules?.minimum_stake ?? 1),
    kind: config.strategy?.kind ?? "mix",
    components: (config.strategy?.components ?? []).map(({ system, percent }) => ({ system, percent: String(percent) })),
    coverage: String(config.strategy?.coverage ?? 10),
    capital: String(config.conditions?.capital ?? 2000),
    goal: String(config.conditions?.goal ?? 2800),
    maxDraws: config.conditions?.max_draws == null ? "" : String(config.conditions.max_draws),
    startDate: config.window?.start_date ?? "", endDate: config.window?.end_date ?? "",
    historySha: base ? base.config.history.sha256 : options.defaults.history_sha256 ?? options.history.sha256,
  };
}

function isISODate(value: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const date = new Date(`${value}T00:00:00Z`);
  return !Number.isNaN(date.valueOf()) && date.toISOString().slice(0, 10) === value;
}
function integerError(value: string, label: string, minimum: number, maximum?: number): string | undefined {
  if (!value || parseIntegerInput(value) === null) return `${label}: ingresá un número entero válido.`;
  const number = parseIntegerInput(value)!;
  if (number < minimum || (maximum !== undefined && number > maximum)) return `${label}: debe estar entre ${minimum} y ${maximum ?? "un valor válido"}.`;
}

export function validateRunForm(form: RunForm, options: RunOptions): { errors: RunFormErrors; valid: boolean } {
  const errors: RunFormErrors = {};
  if (form.name.trim().length > options.limits.name) errors.name = `El nombre admite hasta ${options.limits.name} caracteres.`;
  const positions = parseIntegerInput(form.positions);
  if (positions === null || positions < options.limits.positions.min || positions > options.limits.positions.max) errors.positions = "Elegí entre 1 y 5 posiciones.";
  (positions !== null ? resizePrizes(form.prizes, Math.max(0, Math.min(positions, 5))) : []).forEach((value, index) => {
    const error = integerError(value, `Premio ${index + 1}`, 1);
    if (error) errors.prizes = error;
  });
  const minStake = parseIntegerInput(form.minimumStake);
  if (integerError(form.minimumStake, "La apuesta mínima", 1)) errors.minimumStake = integerError(form.minimumStake, "La apuesta mínima", 1);
  const coverage = parseIntegerInput(form.coverage);
  const coverageError = integerError(form.coverage, "La cobertura", options.limits.coverage.min, options.limits.coverage.max);
  if (coverageError) errors.coverage = "La cobertura debe ser un entero entre 1 y 50.";
  const capital = parseIntegerInput(form.capital), goal = parseIntegerInput(form.goal);
  if (integerError(form.capital, "El capital", 1)) errors.capital = "El capital debe ser un entero de al menos RD$1.";
  else if (coverage !== null && minStake !== null && capital! < coverage * minStake) errors.capital = "El capital debe cubrir al menos una apuesta (cobertura × apuesta mínima).";
  if (integerError(form.goal, "La meta", 2)) errors.goal = "La meta debe ser un entero mayor que cero.";
  else if (capital !== null && goal! <= capital) errors.goal = "La meta debe ser superior al capital.";
  if (form.maxDraws && integerError(form.maxDraws, "La duración máxima", 1)) errors.maxDraws = "La duración máxima debe ser un entero de al menos 1 o quedar vacía.";
  if (form.startDate && !isISODate(form.startDate)) errors.startDate = "Ingresá una fecha válida.";
  if (form.endDate && !isISODate(form.endDate)) errors.endDate = "Ingresá una fecha válida.";
  if (form.startDate && form.endDate && isISODate(form.startDate) && isISODate(form.endDate) && form.startDate > form.endDate) errors.endDate = "La fecha final debe ser igual o posterior a la inicial.";
  if (form.kind === "mix") {
    if (form.components.length < 1 || form.components.length > 13) errors.components = "La mezcla necesita entre 1 y 13 sistemas.";
    const ids = form.components.map((item) => item.system);
    if (new Set(ids).size !== ids.length) errors.components = "No repitas sistemas en la mezcla.";
    if (ids.some((id) => !options.systems.some((system) => system.id === id))) errors.components = "Elegí sistemas disponibles.";
    const percentages = form.components.map((item) => parseIntegerInput(item.percent));
    if (percentages.some((value) => value === null || value < 1 || value > 100)) errors.components = "Cada porcentaje debe ser un entero entre 1 y 100.";
    else if (percentages.reduce<number>((sum, value) => sum + Number(value), 0) !== 100) errors.components = "Los porcentajes de la mezcla deben sumar 100 %.";
  }
  return { errors, valid: Object.keys(errors).length === 0 };
}

export function toCreateRunRequest(form: RunForm, _options: RunOptions): CreateRunRequest {
  return {
    name: form.name.trim() || null,
    rules: { positions: Number(form.positions), prizes: form.prizes.slice(0, Number(form.positions)).map(Number), minimum_stake: Number(form.minimumStake) },
    strategy: { kind: form.kind, components: form.kind === "mix" ? form.components.map(({ system, percent }) => ({ system, percent: Number(percent) })) : [], coverage: Number(form.coverage) },
    conditions: { capital: Number(form.capital), goal: Number(form.goal), max_draws: form.maxDraws === "" ? null : Number(form.maxDraws) },
    window: { start_date: form.startDate || null, end_date: form.endDate || null }, history_sha256: form.historySha,
  };
}
