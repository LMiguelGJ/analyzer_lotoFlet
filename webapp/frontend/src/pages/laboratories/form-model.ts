import type { LaboratoryConfig, StakeStyle } from "../../api/laboratories";

export const SYSTEMS = [
  { value: "transition", label: "Transición" },
  { value: "cold", label: "Fríos" },
  { value: "select_interpretable", label: "Selector interpretable" },
  { value: "mix", label: "Mezclas" },
  { value: "ensemble", label: "Ensemble" },
  { value: "parity", label: "Paridad" },
] as const;
export const STAKE_STYLES: { value: StakeStyle; label: string }[] = [
  { value: "bold", label: "Audaz" },
  { value: "ladder", label: "Escalera" },
  { value: "flat", label: "Plana" },
];

export const PRIZE_FIELDS = ["prize_1", "prize_2", "prize_3", "prize_4", "prize_5"] as const;
export type FormField =
  | "name" | "system" | "coverage" | "stake_style" | "capital" | "goal"
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
  prize_1: "80", prize_2: "8", prize_3: "4", prize_4: "2", prize_5: "1",
  window_start: "2025-09-02 05:10",
  window_end: "2026-09-25 18:20",
};

const MAX_NAME_BYTES = 120;
const SAFE_MAX = Number.MAX_SAFE_INTEGER;
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

export type ParseResult =
  | { ok: true; value: { name: string; config: LaboratoryConfig } }
  | { ok: false; errors: FormErrors };

/** Client-side mirror of the server rules; the server remains the authority. */
export function parseLaboratoryForm(values: FormValues): ParseResult {
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

  const prizes = PRIZE_FIELDS.map((field) => {
    const prize = positiveInt(values[field]);
    if (prize === null) errors[field] = "El premio es un entero positivo.";
    return prize;
  });
  if (!errors.prize_1 && prizes[0] !== null && coverage !== null && values.stake_style !== "flat" && prizes[0] <= coverage) {
    errors.prize_1 = "El primer premio debe ser mayor que la cobertura.";
  }

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
      },
    },
  };
}
