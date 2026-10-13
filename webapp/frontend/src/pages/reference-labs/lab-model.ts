import type { ReferenceLab } from "../../api/referenceLabs";

const SYSTEM_LABELS: Record<string, string> = {
  transition: "Transición",
  cold: "Fríos",
  select_interpretable: "Selector interpretable",
  mix: "Mezclas",
  ensemble: "Ensemble",
  parity: "Paridad",
};
const STAKE_LABELS: Record<ReferenceLab["stake_style"], string> = {
  bold: "Audaz",
  ladder: "Escalera",
  flat: "Plana",
};
export function systemLabel(system: string): string {
  return SYSTEM_LABELS[system] ?? system;
}
export function stakeLabel(style: ReferenceLab["stake_style"]): string {
  return STAKE_LABELS[style];
}
export function labTitle(lab: ReferenceLab): string {
  return `${systemLabel(lab.system)} · ${lab.coverage} ${lab.coverage === 1 ? "número" : "números"} · ${stakeLabel(lab.stake_style)}`;
}
