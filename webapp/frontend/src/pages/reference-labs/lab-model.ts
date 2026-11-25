import type { ReferenceLab } from "../../api/referenceLabs";

const SYSTEM_LABELS: Record<string, string> = {
  transition: "Transición",
  cold: "Fríos",
  select_interpretable: "Selector interpretable",
  mix: "Mezclas",
  ensemble: "Ensemble",
  parity: "Paridad",
  freq_hist: "Frecuencia histórica",
  freq_recent: "Frecuencia reciente",
  decay: "Decaimiento",
  overdue: "Ciclo vencido",
  digits: "Terminaciones y decenas",
};
const STAKE_LABELS: Record<string, string> = {
  bold: "Audaz",
  ladder: "Escalera",
  flat: "Plana",
  martingale: "Martingala",
  paroli: "Paroli",
  dalembert: "D'Alembert",
  fibonacci: "Fibonacci",
  oscars_grind: "Oscar's Grind",
};
export function systemLabel(system: string): string {
  return SYSTEM_LABELS[system] ?? system;
}
export function stakeLabel(style: string): string {
  return STAKE_LABELS[style] ?? style;
}
export function labTitle(lab: ReferenceLab): string {
  return `${systemLabel(lab.system)} · ${lab.coverage} ${lab.coverage === 1 ? "número" : "números"} · ${stakeLabel(lab.stake_style)}`;
}
